import sys,time,json,logging,asyncio,argparse,signal,os
import cv2,numpy as np,av,sounddevice as sd
import paho.mqtt.client as mqtt
from aiortc import RTCPeerConnection,RTCConfiguration,RTCIceServer,RTCSessionDescription,VideoStreamTrack
from aiortc.sdp import candidate_from_sdp
Dev_cfg={"dev_id":"pi4_01","brk_url":"broker.emqx.io","brk_prt":1883,"cam_idx":1,"dist_lim":80.0,"spk_vol":80,"alt_frq":2000,"fps_num":15,"trig_pin":23,"echo_pin":24,"tel_int":3.0,"prev_vol":80}
Sen_dat={"bat_pct":100,"temp_c":0.0,"cpu_pct":0.0,"dist_cm":-1.0,"cam_on":False,"alt_on":False,"last_alt":0.0}
Cli_mq=None
Pc_set=set()
Ice_buf=[]
Vid_trk=None
Aud_snk=None
Hcsr_obj=None
Evt_lop=None
Is_run=True
Last_cpu=[0,0]
Log_fmt=logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s","%H:%M:%S")
Log_hdl=logging.StreamHandler(sys.stdout)
Log_hdl.setFormatter(Log_fmt)
Logger=logging.getLogger("pi_server")
Logger.setLevel(logging.INFO)
Logger.addHandler(Log_hdl)
def log_inf(msg):
	Logger.info(msg)
def log_wrn(msg):
	Logger.warning(msg)
def log_err(msg):
	Logger.error(msg)
def get_tmp():
	try:
		if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
			with open("/sys/class/thermal/thermal_zone0/temp","r") as fil:
				return round(float(fil.read().strip())/1000.0,1)
	except Exception:
		pass
	return 0.0
def get_cpu():
	global Last_cpu
	try:
		if os.path.exists("/proc/stat"):
			with open("/proc/stat","r") as fil:
				lin=fil.readline()
			tok=lin.strip().split()[1:5]
			tot=sum(int(x) for x in tok)
			idl=int(tok[3])
			d_tot=tot-Last_cpu[0]
			d_idl=idl-Last_cpu[1]
			Last_cpu=[tot,idl]
			if d_tot>0: return round((1.0-(d_idl/float(d_tot)))*100.0,1)
	except Exception:
		pass
	return 0.0
class AudSnk:
	def __init__(self):
		self._strm=None
		try:
			dev_lst=sd.query_devices()
			if len(dev_lst)>0:
				self._strm=sd.OutputStream(samplerate=48000,channels=1,dtype='int16')
				self._strm.start()
		except Exception as err:
			self._strm=None
			log_wrn(f"Speaker output device not available: {err}")
	async def consume(self,trk):
		pkg_cnt=0
		while Is_run:
			try:
				frm=await trk.recv()
			except Exception:
				break
			arr_dat=frm.to_ndarray()
			pkg_cnt+=1
			if self._strm is not None:
				try:
					pcm_dat=arr_dat.T if arr_dat.shape[0]<arr_dat.shape[1] else arr_dat
					if pcm_dat.dtype!=np.int16:
						pcm_dat=(pcm_dat*32767).astype(np.int16)
					await Evt_lop.run_in_executor(None,self._strm.write,pcm_dat)
				except Exception:
					pass
			if pkg_cnt%30==1:
				rms_val=float(np.sqrt(np.mean(arr_dat.astype(np.float32)**2)))
				log_inf(f"[PTT Audio] Frame #{pkg_cnt}: {frm.samples} samples, RMS={rms_val:.2f}")
	def close(self):
		if self._strm is not None:
			try:
				self._strm.stop()
				self._strm.close()
			except Exception:
				pass
			self._strm=None
class HcsrDrvr:
	def __init__(self,trig_pin=23,echo_pin=24):
		self.trig_pin=trig_pin
		self.echo_pin=echo_pin
		self.is_hw=False
		self.gpio=None
		try:
			import RPi.GPIO as GPIO
			self.gpio=GPIO
			self.gpio.setwarnings(False)
			self.gpio.setmode(self.gpio.BCM)
			self.gpio.setup(self.trig_pin,self.gpio.OUT)
			self.gpio.setup(self.echo_pin,self.gpio.IN)
			self.gpio.output(self.trig_pin,self.gpio.LOW)
			self.is_hw=True
			log_inf(f"Initialized real HC-SR04 sensor on GPIO TRIG={trig_pin}, ECHO={echo_pin}")
		except Exception as err:
			self.is_hw=False
			log_wrn(f"HC-SR04 hardware initialization failed: {err}")
	def measure(self):
		if not self.is_hw or self.gpio is None: return -1.0
		try:
			self.gpio.output(self.trig_pin,self.gpio.HIGH)
			time.sleep(0.00001)
			self.gpio.output(self.trig_pin,self.gpio.LOW)
			p_sta=time.time()
			t_max=p_sta+0.03
			while self.gpio.input(self.echo_pin)==self.gpio.LOW:
				p_sta=time.time()
				if p_sta>t_max: return -1.0
			p_end=time.time()
			while self.gpio.input(self.echo_pin)==self.gpio.HIGH:
				p_end=time.time()
				if p_end>t_max: return -1.0
			dst_cm=round(((p_end-p_sta)*34300.0)/2.0,1)
			if 3.0<=dst_cm<=400.0: return dst_cm
			return -1.0
		except Exception:
			return -1.0
	def close(self):
		if self.is_hw and self.gpio is not None:
			try:
				self.gpio.cleanup([self.trig_pin,self.echo_pin])
			except Exception:
				pass
class PiCamTrk(VideoStreamTrack):
	def __init__(self,cam_idx=1):
		super().__init__()
		self.cam_idx=cam_idx
		self._cam=None
		self._try_cam()
	def _try_cam(self):
		cand_lst=[self.cam_idx]+[i for i in (1,0,2) if i!=self.cam_idx]
		for cur_idx in cand_lst:
			try:
				cap_obj=cv2.VideoCapture(cur_idx,cv2.CAP_V4L2) if hasattr(cv2,"CAP_V4L2") else cv2.VideoCapture(cur_idx)
				if cap_obj.isOpened():
					try:
						cap_obj.set(cv2.CAP_PROP_BUFFERSIZE,1)
						cap_obj.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*"MJPG"))
						cap_obj.set(cv2.CAP_PROP_FRAME_WIDTH,640)
						cap_obj.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
						cap_obj.set(cv2.CAP_PROP_FPS,30)
					except Exception:
						pass
					ret_val,tst_frm=cap_obj.read()
					if ret_val and tst_frm is not None:
						self._cam=cap_obj
						self.cam_idx=cur_idx
						log_inf(f"Opened real hardware webcam on index {cur_idx}")
						return
					cap_obj.release()
			except Exception:
				pass
		log_wrn("Real webcam not available or occupied by another process.")
	async def recv(self):
		pts_val,tb_val=await self.next_timestamp()
		frm_img=None
		if self._cam is None:
			self._try_cam()
		if self._cam is not None:
			try:
				ret_val,raw_frm=await Evt_lop.run_in_executor(None,self._cam.read)
				if ret_val and raw_frm is not None:
					frm_img=cv2.resize(raw_frm,(640,480))
					self._drw_hud(frm_img)
				else:
					self._cam.release()
					self._cam=None
			except Exception:
				self._cam=None
		if frm_img is None:
			frm_img=self._drw_blk()
		vid_frm=av.VideoFrame.from_ndarray(frm_img,format="bgr24")
		vid_frm.pts=pts_val
		vid_frm.time_base=tb_val
		return vid_frm
	def _drw_hud(self,img):
		cv2.rectangle(img,(0,455),(640,480),(0,0,0),-1)
		dst_val=Sen_dat["dist_cm"]
		lim_val=Dev_cfg["dist_lim"]
		is_dng=0.0<=dst_val<lim_val
		col_txt=(0,0,255) if is_dng else ((0,255,255) if dst_val>=0.0 else (160,160,160))
		dst_str=f"{dst_val:.1f}cm" if dst_val>=0.0 else "N/A (Chua ket noi)"
		txt_hud=f"DEV:{Dev_cfg['dev_id']} | BAT:{Sen_dat['bat_pct']}% | TMP:{Sen_dat['temp_c']:.1f}C | DIST:{dst_str}"
		cv2.putText(img,txt_hud,(10,472),cv2.FONT_HERSHEY_SIMPLEX,0.45,col_txt,1)
		if is_dng:
			cv2.rectangle(img,(0,0),(639,479),(0,0,255),4)
			cv2.putText(img,f"! OBSTACLE HAZARD: {dst_val:.1f}cm !",(130,30),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,0,255),2)
	def _drw_blk(self):
		img=np.full((480,640,3),(20,20,24),dtype=np.uint8)
		cv2.rectangle(img,(20,20),(620,460),(45,45,55),1)
		cv2.circle(img,(320,180),40,(60,60,70),2)
		cv2.line(img,(290,150),(350,210),(0,0,220),3)
		cv2.putText(img,"CAMERA KHONG KHA DUNG",(170,260),cv2.FONT_HERSHEY_SIMPLEX,0.7,(220,220,220),2)
		cv2.putText(img,"Webcam chua cam hoac dang bi tien trinh khac chiem dung",(75,295),cv2.FONT_HERSHEY_SIMPLEX,0.45,(150,150,160),1)
		cv2.putText(img,"Vui long kiem tra cong USB hoac tat AI main.py de giai phong",(70,325),cv2.FONT_HERSHEY_SIMPLEX,0.45,(150,150,160),1)
		cv2.rectangle(img,(0,455),(640,480),(10,10,12),-1)
		dst_val=Sen_dat["dist_cm"]
		dst_str=f"{dst_val:.1f}cm" if dst_val>=0.0 else "N/A"
		txt_hud=f"DEV:{Dev_cfg['dev_id']} | BAT:{Sen_dat['bat_pct']}% | TMP:{Sen_dat['temp_c']:.1f}C | DIST:{dst_str}"
		cv2.putText(img,txt_hud,(10,472),cv2.FONT_HERSHEY_SIMPLEX,0.42,(160,160,160),1)
		tim_str=time.strftime("%H:%M:%S",time.localtime())
		cv2.putText(img,tim_str,(560,472),cv2.FONT_HERSHEY_SIMPLEX,0.42,(160,160,160),1)
		return img
	def close(self):
		if self._cam is not None:
			try:
				self._cam.release()
			except Exception:
				pass
			self._cam=None
def chk_alt(forced=False):
	cur_dst=Sen_dat["dist_cm"]
	if cur_dst<0.0 and not forced:
		Sen_dat["alt_on"]=False
		return
	lim_dst=Dev_cfg["dist_lim"]
	now_ms=time.time()*1000.0
	is_dng=cur_dst<lim_dst or forced
	if is_dng:
		is_cok=(now_ms-Sen_dat["last_alt"])>=Dev_cfg["alt_frq"]
		if is_cok or not Sen_dat["alt_on"] or forced:
			Sen_dat["last_alt"]=now_ms
			Sen_dat["alt_on"]=True
			lvl_str="CRITICAL" if cur_dst<40.0 else "WARNING"
			obj_lst=["stairs_down","obstacle"] if cur_dst<40.0 else ["obstacle"]
			msg_str=f"Phat hien vat can o cu ly gan: {cur_dst:.1f} cm!"
			alt_obj={"event_id":f"evt_{int(now_ms)%1000000}","timestamp":int(time.time()),"alert_type":"OBSTACLE_DANGER","level":lvl_str,"distance_cm":round(cur_dst,1),"detected_objects":obj_lst,"message":msg_str}
			Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/alert",json.dumps(alt_obj),qos=1)
			log_wrn(f"[ALERT] Level: {lvl_str}, Dist: {cur_dst:.1f}cm")
	else:
		Sen_dat["alt_on"]=False
def hdl_cfg(raw_pay):
	try:
		dat_obj=json.loads(raw_pay)
		if not isinstance(dat_obj,dict): return
		if "distance_threshold_cm" in dat_obj:
			Dev_cfg["dist_lim"]=max(0.0,float(dat_obj["distance_threshold_cm"]))
		if "speaker_volume" in dat_obj:
			Dev_cfg["spk_vol"]=max(0,min(100,int(dat_obj["speaker_volume"])))
		if "alert_frequency_ms" in dat_obj:
			Dev_cfg["alt_frq"]=max(100,int(dat_obj["alert_frequency_ms"]))
		if "detection_fps" in dat_obj:
			Dev_cfg["fps_num"]=max(1,min(60,int(dat_obj["detection_fps"])))
		log_inf(f"Config updated: threshold={Dev_cfg['dist_lim']}cm, volume={Dev_cfg['spk_vol']}%, freq={Dev_cfg['alt_frq']}ms")
	except Exception as err:
		log_err(f"Config parsing error: {err}")
async def hdl_cmd(raw_pay):
	try:
		dat_obj=json.loads(raw_pay)
		cmd_str=dat_obj.get("command","").strip().upper()
		log_inf(f"Received command: {cmd_str}")
		if cmd_str=="REBOOT":
			log_inf("Initiating system reboot...")
			now_ts=int(time.time())
			Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/status",json.dumps({"status":"offline","timestamp":now_ts}),qos=1,retain=True)
			os.system("sudo reboot || true")
		elif cmd_str=="RESTART_SERVICE":
			log_inf("Restarting WebRTC connections...")
			for cur_pc in list(Pc_set):
				try:
					await cur_pc.close()
				except Exception:
					pass
			Pc_set.clear()
			Sen_dat["cam_on"]=False
		elif cmd_str=="MUTE":
			Dev_cfg["prev_vol"]=Dev_cfg["spk_vol"]
			Dev_cfg["spk_vol"]=0
			log_inf("Speaker muted")
		elif cmd_str=="UNMUTE":
			Dev_cfg["spk_vol"]=Dev_cfg["prev_vol"] if Dev_cfg["prev_vol"]>0 else 80
			log_inf(f"Speaker unmuted, volume restored to {Dev_cfg['spk_vol']}")
		elif cmd_str=="TRIGGER_BUZZER":
			log_inf("Triggering buzzer signal...")
			sys.stdout.write('\a')
			sys.stdout.flush()
	except Exception as err:
		log_err(f"Exception in hdl_cmd: {err}")
async def hdl_ofr(raw_pay):
	try:
		dat_obj=json.loads(raw_pay)
		sdp_str=dat_obj.get("sdp")
		typ_str=dat_obj.get("type","offer")
		if not sdp_str:
			log_err("Offer missing sdp field")
			return
		for cur_pc in list(Pc_set):
			try:
				await cur_pc.close()
			except Exception:
				pass
		Pc_set.clear()
		cfg_rtc=RTCConfiguration(iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
		new_pc=RTCPeerConnection(configuration=cfg_rtc)
		Pc_set.add(new_pc)
		new_pc.addTrack(Vid_trk)
		@new_pc.on("track")
		def on_trk(trk):
			if trk.kind=="audio":
				asyncio.create_task(Aud_snk.consume(trk))
		@new_pc.on("connectionstatechange")
		async def on_stt():
			log_inf(f"WebRTC connection state: {new_pc.connectionState}")
			if new_pc.connectionState in ("failed","closed","disconnected"):
				Sen_dat["cam_on"]=False
				Pc_set.discard(new_pc)
				try:
					await new_pc.close()
				except Exception:
					pass
			elif new_pc.connectionState=="connected":
				Sen_dat["cam_on"]=True
		await new_pc.setRemoteDescription(RTCSessionDescription(sdp=sdp_str,type=typ_str))
		for cand_obj in Ice_buf:
			try:
				await new_pc.addIceCandidate(cand_obj)
			except Exception as err:
				log_err(f"ICE candidate error: {err}")
		Ice_buf.clear()
		ans_rtc=await new_pc.createAnswer()
		await new_pc.setLocalDescription(ans_rtc)
		ans_pay=json.dumps({"sdp":new_pc.localDescription.sdp,"type":"answer","callee":Dev_cfg["dev_id"]})
		Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/webrtc/answer",ans_pay,qos=1)
		log_inf(f"Sent SDP Answer to pbl6/{Dev_cfg['dev_id']}/webrtc/answer")
	except Exception as err:
		log_err(f"Exception in hdl_ofr: {err}")
async def hdl_ice(raw_pay):
	try:
		dat_obj=json.loads(raw_pay)
		if dat_obj.get("sender") in ("pi",Dev_cfg["dev_id"]): return
		raw_c=dat_obj.get("candidate")
		if not raw_c: return
		if raw_c.startswith("candidate:"):
			raw_c=raw_c[10:]
		cand_obj=candidate_from_sdp(raw_c)
		cand_obj.sdpMid=dat_obj.get("sdpMid")
		cand_obj.sdpMLineIndex=dat_obj.get("sdpMLineIndex")
		if len(Pc_set)>0:
			for cur_pc in Pc_set:
				await cur_pc.addIceCandidate(cand_obj)
		else:
			Ice_buf.append(cand_obj)
	except Exception as err:
		log_err(f"Failed to add ICE candidate: {err}")
def on_con(cli,ud,flg,*args):
	rc_val=args[0] if args else 0
	if hasattr(rc_val,"is_failure") and rc_val.is_failure:
		log_err(f"MQTT connection failed: {rc_val}")
		return
	log_inf(f"Connected to MQTT broker {Dev_cfg['brk_url']}:{Dev_cfg['brk_prt']}")
	dev_id=Dev_cfg["dev_id"]
	sub_top=[(f"pbl6/{dev_id}/config",1),(f"pbl6/{dev_id}/command",1),(f"pbl6/{dev_id}/webrtc/offer",1),(f"pbl6/{dev_id}/webrtc/ice_candidate",1)]
	cli.subscribe(sub_top)
	now_ts=int(time.time())
	cli.publish(f"pbl6/{dev_id}/status",json.dumps({"status":"online","timestamp":now_ts}),qos=1,retain=True)
	log_inf(f"Published online status to pbl6/{dev_id}/status")
def on_msg(cli,ud,msg):
	try:
		top_str=msg.topic
		pay_str=msg.payload.decode("utf-8",errors="replace")
	except Exception as err:
		log_err(f"Failed to decode MQTT payload: {err}")
		return
	if Evt_lop is None or Evt_lop.is_closed(): return
	dev_id=Dev_cfg["dev_id"]
	if top_str==f"pbl6/{dev_id}/config":
		Evt_lop.call_soon_threadsafe(hdl_cfg,pay_str)
	elif top_str==f"pbl6/{dev_id}/command":
		asyncio.run_coroutine_threadsafe(hdl_cmd(pay_str),Evt_lop)
	elif top_str==f"pbl6/{dev_id}/webrtc/offer":
		asyncio.run_coroutine_threadsafe(hdl_ofr(pay_str),Evt_lop)
	elif top_str==f"pbl6/{dev_id}/webrtc/ice_candidate":
		asyncio.run_coroutine_threadsafe(hdl_ice(pay_str),Evt_lop)
async def tel_lop(interval=3.0):
	log_inf(f"Hardware telemetry publication started (interval={interval}s)")
	while Is_run:
		now_ts=int(time.time())
		Sen_dat["temp_c"]=get_tmp()
		Sen_dat["cpu_pct"]=get_cpu()
		Sen_dat["dist_cm"]=Hcsr_obj.measure() if Hcsr_obj else -1.0
		tel_obj={
			"device_id":Dev_cfg["dev_id"],
			"timestamp":now_ts,
			"battery_percentage":int(Sen_dat["bat_pct"]),
			"temperature_celsius":Sen_dat["temp_c"],
			"cpu_usage":Sen_dat["cpu_pct"],
			"ultrasonic_distance_cm":Sen_dat["dist_cm"],
			"camera_active":bool(Sen_dat["cam_on"]),
			"speaker_volume":int(Dev_cfg["spk_vol"])
		}
		Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/telemetry",json.dumps(tel_obj),qos=0)
		chk_alt()
		await asyncio.sleep(interval)
def req_ext():
	global Is_run
	Is_run=False
	if Evt_lop and not Evt_lop.is_closed():
		Evt_lop.call_soon_threadsafe(Evt_lop.stop)
def sig_hdl(sig,frm):
	log_inf(f"Received signal ({sig}), shutting down cleanly...")
	req_ext()
def parse_arg():
	prs=argparse.ArgumentParser(description="Raspberry Pi 4 Hardware Server for PBL6 Assistive Monitor")
	prs.add_argument("--device-id",default="pi4_01",help="MQTT device ID (default: pi4_01)")
	prs.add_argument("--broker",default="broker.emqx.io",help="MQTT broker host (default: broker.emqx.io)")
	prs.add_argument("--port",type=int,default=1883,help="MQTT broker port (default: 1883)")
	prs.add_argument("--camera-index",type=int,default=1,help="Hardware USB camera index (default: 1)")
	prs.add_argument("--interval",type=float,default=3.0,help="Telemetry interval in seconds (default: 3.0)")
	prs.add_argument("--trig-pin",type=int,default=23,help="HC-SR04 trigger GPIO pin (default: 23)")
	prs.add_argument("--echo-pin",type=int,default=24,help="HC-SR04 echo GPIO pin (default: 24)")
	return prs.parse_args()
async def run_srv():
	global Vid_trk,Aud_snk,Cli_mq,Evt_lop,Hcsr_obj
	Evt_lop=asyncio.get_running_loop()
	Vid_trk=PiCamTrk(cam_idx=Dev_cfg["cam_idx"])
	Aud_snk=AudSnk()
	Hcsr_obj=HcsrDrvr(trig_pin=Dev_cfg["trig_pin"],echo_pin=Dev_cfg["echo_pin"])
	cid=f"{Dev_cfg['dev_id']}_hw_{int(time.time()*1000)%100000}"
	try:
		Cli_mq=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=cid)
	except AttributeError:
		Cli_mq=mqtt.Client(client_id=cid)
	Cli_mq.on_connect=on_con
	Cli_mq.on_message=on_msg
	dev_id=Dev_cfg["dev_id"]
	lwt_pay=json.dumps({"status":"offline","timestamp":int(time.time())})
	Cli_mq.will_set(f"pbl6/{dev_id}/status",lwt_pay,qos=1,retain=True)
	log_inf(f"Connecting to MQTT broker {Dev_cfg['brk_url']}:{Dev_cfg['brk_prt']} as {cid}...")
	Cli_mq.connect(Dev_cfg["brk_url"],Dev_cfg["brk_prt"],keepalive=60)
	Cli_mq.loop_start()
	tsk_tel=asyncio.create_task(tel_lop(interval=Dev_cfg["tel_int"]))
	try:
		while Is_run:
			await asyncio.sleep(0.5)
	except asyncio.CancelledError:
		pass
	finally:
		log_inf("Stopping Raspberry Pi hardware service...")
		tsk_tel.cancel()
		now_ts=int(time.time())
		Cli_mq.publish(f"pbl6/{dev_id}/status",json.dumps({"status":"offline","timestamp":now_ts}),qos=1,retain=True)
		for cur_pc in list(Pc_set):
			try:
				await cur_pc.close()
			except Exception:
				pass
		Pc_set.clear()
		if Hcsr_obj is not None:
			Hcsr_obj.close()
		Vid_trk.close()
		Aud_snk.close()
		Cli_mq.loop_stop()
		Cli_mq.disconnect()
		log_inf("Raspberry Pi hardware service stopped.")
def main():
	sig_lst=[signal.SIGINT]
	if hasattr(signal,"SIGTERM"):
		sig_lst.append(signal.SIGTERM)
	for cur_sig in sig_lst:
		try:
			signal.signal(cur_sig,sig_hdl)
		except Exception:
			pass
	arg_obj=parse_arg()
	Dev_cfg["dev_id"]=arg_obj.device_id
	Dev_cfg["brk_url"]=arg_obj.broker
	Dev_cfg["brk_prt"]=arg_obj.port
	Dev_cfg["cam_idx"]=arg_obj.camera_index
	Dev_cfg["tel_int"]=arg_obj.interval
	Dev_cfg["trig_pin"]=arg_obj.trig_pin
	Dev_cfg["echo_pin"]=arg_obj.echo_pin
	try:
		asyncio.run(run_srv())
	except (KeyboardInterrupt,SystemExit):
		pass
if __name__=="__main__":
	main()

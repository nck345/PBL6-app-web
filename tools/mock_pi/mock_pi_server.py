import sys,time,json,math,random,logging,asyncio,argparse,signal,fractions
import cv2,numpy as np,av,sounddevice as sd
import paho.mqtt.client as mqtt
from aiortc import RTCPeerConnection,RTCConfiguration,RTCIceServer,RTCSessionDescription,VideoStreamTrack
from aiortc.sdp import candidate_from_sdp
Dev_cfg={"dev_id":"pi4_01","brk_url":"broker.hivemq.com","brk_prt":1883,"cam_idx":0,"syn_mod":False,"hed_mod":False,"dist_lim":80.0,"spk_vol":80,"alt_frq":2000,"fps_num":15,"man_dst":False,"prev_vol":80}
Sen_dat={"bat_pct":85.0,"temp_c":48.5,"cpu_pct":32.0,"dist_cm":145.2,"cam_on":False,"alt_on":False,"last_alt":0.0}
Cli_mq=None
Pc_set=set()
Ice_buf=[]
Vid_trk=None
Aud_snk=None
Evt_lop=None
Is_run=True
Log_fmt=logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s","%H:%M:%S")
Log_hdl=logging.StreamHandler(sys.stdout)
Log_hdl.setFormatter(Log_fmt)
Logger=logging.getLogger("mock_pi")
Logger.setLevel(logging.INFO)
Logger.addHandler(Log_hdl)
def log_inf(msg):
	Logger.info(msg)
def log_wrn(msg):
	Logger.warning(msg)
def log_err(msg):
	Logger.error(msg)
class AudSnk:
	def __init__(self):
		self._strm=None
		self.use_mco=False
		try:
			dev_lst=sd.query_devices()
			if len(dev_lst)>0:
				self._strm=sd.OutputStream(samplerate=48000,channels=1,dtype='int16')
				self._strm.start()
		except Exception:
			self.use_mco=True
			self._strm=None
	async def consume(self,trk):
		pkg_cnt=0
		while Is_run:
			try:
				frm=await trk.recv()
			except Exception:
				break
			arr_dat=frm.to_ndarray()
			rms_val=float(np.sqrt(np.mean(arr_dat.astype(np.float32)**2)))
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
				log_inf(f"[PTT Audio] Frame #{pkg_cnt}: {frm.samples} samples, RMS={rms_val:.2f}")
	def close(self):
		if self._strm is not None:
			try:
				self._strm.stop()
				self._strm.close()
			except Exception:
				pass
			self._strm=None
class PiVidTrk(VideoStreamTrack):
	def __init__(self,cam_idx=0,syn_mod=False):
		super().__init__()
		self.cam_idx=cam_idx
		self.syn_mod=syn_mod
		self._cam=None
		if not syn_mod:
			try:
				self._cam=cv2.VideoCapture(cam_idx)
				if not self._cam.isOpened():
					self._cam=None
			except Exception:
				self._cam=None
	async def recv(self):
		pts_val,tb_val=await self.next_timestamp()
		frm_img=None
		if self._cam is not None:
			try:
				ret_val,raw_frm=await Evt_lop.run_in_executor(None,self._cam.read)
				if ret_val and raw_frm is not None:
					frm_img=cv2.resize(raw_frm,(640,480))
					self._drw_cam(frm_img)
			except Exception:
				frm_img=None
		if frm_img is None:
			frm_img=self._drw_syn()
		vid_frm=av.VideoFrame.from_ndarray(frm_img,format="bgr24")
		vid_frm.pts=pts_val
		vid_frm.time_base=tb_val
		return vid_frm
	def _drw_cam(self,img):
		cv2.rectangle(img,(0,455),(640,480),(0,0,0),-1)
		dst_val=Sen_dat["dist_cm"]
		lim_val=Dev_cfg["dist_lim"]
		is_dng=dst_val<lim_val
		col_txt=(0,0,255) if is_dng else (0,255,255)
		txt_hud=f"DEV:{Dev_cfg['dev_id']} | BAT:{int(Sen_dat['bat_pct'])}% | TMP:{Sen_dat['temp_c']:.1f}C | DIST:{dst_val:.1f}cm"
		cv2.putText(img,txt_hud,(10,472),cv2.FONT_HERSHEY_SIMPLEX,0.45,col_txt,1)
		if is_dng:
			cv2.rectangle(img,(0,0),(639,479),(0,0,255),4)
			cv2.putText(img,f"! OBSTACLE HAZARD: {dst_val:.1f}cm !",(130,30),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,0,255),2)
	def _drw_syn(self):
		img=np.full((480,640,3),(16,22,16),dtype=np.uint8)
		cv2.circle(img,(320,240),40,(0,70,0),1)
		cv2.circle(img,(320,240),80,(0,90,0),1)
		cv2.circle(img,(320,240),120,(0,110,0),1)
		cv2.circle(img,(320,240),160,(0,130,0),1)
		cv2.circle(img,(320,240),200,(0,160,0),2)
		cv2.line(img,(120,240),(520,240),(0,90,0),1)
		cv2.line(img,(320,40),(320,440),(0,90,0),1)
		cv2.putText(img,"50cm",(325,200),cv2.FONT_HERSHEY_SIMPLEX,0.35,(0,120,0),1)
		cv2.putText(img,"100cm",(325,160),cv2.FONT_HERSHEY_SIMPLEX,0.35,(0,120,0),1)
		cv2.putText(img,"150cm",(325,120),cv2.FONT_HERSHEY_SIMPLEX,0.35,(0,120,0),1)
		cv2.putText(img,"200cm",(325,80),cv2.FONT_HERSHEY_SIMPLEX,0.35,(0,120,0),1)
		ang_deg=(time.time()*90.0)%360.0
		rad_val=math.radians(ang_deg)
		end_x=int(320+200*math.cos(rad_val))
		end_y=int(240+200*math.sin(rad_val))
		cv2.line(img,(320,240),(end_x,end_y),(0,255,120),2)
		dst_val=Sen_dat["dist_cm"]
		lim_val=Dev_cfg["dist_lim"]
		is_dng=dst_val<lim_val
		rad_blp=int(min(200,max(25,(dst_val/250.0)*200)))
		blp_x=int(320+rad_blp*0.7071)
		blp_y=int(240-rad_blp*0.7071)
		if is_dng:
			is_fls=(int(time.time()*4)%2)==0
			col_blp=(0,0,255) if is_fls else (0,140,255)
			cv2.circle(img,(blp_x,blp_y),8,col_blp,-1)
			cv2.rectangle(img,(blp_x-15,blp_y-15),(blp_x+15,blp_y+15),(0,0,255),2)
			cv2.putText(img,f"! {dst_val:.1f}cm !",(blp_x+18,blp_y+5),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,0,255),1)
			cv2.putText(img,"WARNING: OBSTACLE IN CRITICAL RANGE",(130,25),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,0,255),2)
		else:
			cv2.circle(img,(blp_x,blp_y),6,(0,255,0),-1)
			cv2.putText(img,f"{dst_val:.1f}cm",(blp_x+10,blp_y+5),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,255,0),1)
			cv2.putText(img,f"MOCK PI 4 - SYNTHETIC RADAR ({Dev_cfg['dev_id']})",(140,25),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,255,120),1)
		cv2.rectangle(img,(0,455),(640,480),(10,15,10),-1)
		str_hud=f"BAT:{int(Sen_dat['bat_pct'])}% | TMP:{Sen_dat['temp_c']:.1f}C | CPU:{Sen_dat['cpu_pct']:.1f}% | DIST:{dst_val:.1f}cm | VOL:{Dev_cfg['spk_vol']}%"
		cv2.putText(img,str_hud,(10,472),cv2.FONT_HERSHEY_SIMPLEX,0.42,(180,220,180),1)
		tim_str=time.strftime("%H:%M:%S",time.localtime())
		cv2.putText(img,tim_str,(560,472),cv2.FONT_HERSHEY_SIMPLEX,0.42,(180,220,180),1)
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
			msg_str=f"Phát hiện chướng ngại vật ở cự ly gần: {cur_dst:.1f} cm!"
			alt_obj={"event_id":f"evt_{int(now_ms)%1000000}","timestamp":int(time.time()),"alert_type":"OBSTACLE_DANGER","level":lvl_str,"distance_cm":round(cur_dst,1),"detected_objects":obj_lst,"message":msg_str}
			Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/alert",json.dumps(alt_obj),qos=1)
			log_wrn(f"[ALERT FIRED] Level: {lvl_str}, Dist: {cur_dst:.1f}cm, Msg: {msg_str}")
	else:
		Sen_dat["alt_on"]=False
def hdl_cfg(raw_pay):
	try:
		dat_obj=json.loads(raw_pay)
		if not isinstance(dat_obj,dict):
			log_err(f"Config payload must be a JSON object, got {type(dat_obj).__name__}")
			return
		if "distance_threshold_cm" in dat_obj:
			Dev_cfg["dist_lim"]=max(0.0,float(dat_obj["distance_threshold_cm"]))
		if "speaker_volume" in dat_obj:
			Dev_cfg["spk_vol"]=max(0,min(100,int(dat_obj["speaker_volume"])))
		if "alert_frequency_ms" in dat_obj:
			Dev_cfg["alt_frq"]=max(100,int(dat_obj["alert_frequency_ms"]))
		if "detection_fps" in dat_obj:
			Dev_cfg["fps_num"]=max(1,min(60,int(dat_obj["detection_fps"])))
		log_inf(f"Updated configuration: threshold={Dev_cfg['dist_lim']}cm, volume={Dev_cfg['spk_vol']}%, freq={Dev_cfg['alt_frq']}ms, fps={Dev_cfg['fps_num']}")
	except Exception as err:
		log_err(f"Config parsing error: {err}")
async def hdl_cmd(raw_pay):
	try:
		dat_obj=json.loads(raw_pay)
		cmd_str=dat_obj.get("command","").strip().upper()
		log_inf(f"Received command: {cmd_str}")
		if cmd_str=="REBOOT":
			log_inf("Simulating device reboot...")
			now_ts=int(time.time())
			Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/status",json.dumps({"status":"offline","timestamp":now_ts}),qos=1,retain=True)
			Sen_dat["cam_on"]=False
			await asyncio.sleep(3.0)
			Sen_dat["bat_pct"]=85.0
			Sen_dat["cpu_pct"]=20.0
			Sen_dat["temp_c"]=45.0
			now_ts=int(time.time())
			Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/status",json.dumps({"status":"online","timestamp":now_ts}),qos=1,retain=True)
			log_inf("Reboot simulation complete, device back online")
		elif cmd_str=="RESTART_SERVICE":
			log_inf("Restarting WebRTC service...")
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
			log_inf("Triggering hardware buzzer...")
			try:
				import winsound
				winsound.Beep(1200,300)
			except Exception:
				sys.stdout.write('\a')
				sys.stdout.flush()
	except Exception as err:
		log_err(f"Exception in hdl_cmd: {err}")
async def hdl_ofr(raw_pay):
	try:
		log_inf(f"Handling WebRTC offer (payload len: {len(raw_pay)})...")
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
			log_inf(f"WebRTC PeerConnection state: {new_pc.connectionState}")
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
		log_inf(f"Published SDP Answer to pbl6/{Dev_cfg['dev_id']}/webrtc/answer")
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
	log_inf(f"Subscribed to MQTT topics for device: {dev_id}")
	now_ts=int(time.time())
	cli.publish(f"pbl6/{dev_id}/status",json.dumps({"status":"online","timestamp":now_ts}),qos=1,retain=True)
	log_inf(f"Published online status with retain=True to pbl6/{dev_id}/status")
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
	log_inf(f"Telemetry publication loop started (interval={interval}s)")
	while Is_run:
		now_ts=int(time.time())
		Sen_dat["bat_pct"]=max(10.0,min(100.0,Sen_dat["bat_pct"]-0.01))
		Sen_dat["temp_c"]=round(max(40.0,min(65.0,Sen_dat["temp_c"]+random.uniform(-0.15,0.15))),1)
		base_cpu=22.0+random.uniform(-2.0,3.0)
		if Sen_dat["cam_on"]:
			base_cpu+=35.0
		Sen_dat["cpu_pct"]=round(min(98.0,base_cpu),1)
		if not Dev_cfg["man_dst"]:
			Sen_dat["dist_cm"]=round(max(20.0,min(280.0,Sen_dat["dist_cm"]+random.uniform(-4.0,4.0))),1)
		tel_obj={
			"device_id":Dev_cfg["dev_id"],
			"timestamp":now_ts,
			"battery_percentage":int(round(Sen_dat["bat_pct"])),
			"temperature_celsius":Sen_dat["temp_c"],
			"cpu_usage":Sen_dat["cpu_pct"],
			"ultrasonic_distance_cm":Sen_dat["dist_cm"],
			"camera_active":bool(Sen_dat["cam_on"]),
			"speaker_volume":int(Dev_cfg["spk_vol"])
		}
		Cli_mq.publish(f"pbl6/{Dev_cfg['dev_id']}/telemetry",json.dumps(tel_obj),qos=0)
		chk_alt()
		await asyncio.sleep(interval)
async def cli_lop():
	log_inf("Interactive console ready. Type 'h' for help, 'a' for alert, 'q' to quit.")
	while Is_run:
		try:
			raw_lin=await asyncio.to_thread(sys.stdin.readline)
			if not raw_lin: break
			cmd_lin=raw_lin.strip()
			if not cmd_lin: continue
			tok_lst=cmd_lin.split()
			cmd_op=tok_lst[0].lower()
			if cmd_op in ("q","quit","exit"):
				log_inf("Shutdown requested via console")
				req_ext()
				break
			elif cmd_op in ("a","alert"):
				log_inf("Manual hazard alert triggered via console")
				chk_alt(forced=True)
			elif cmd_op=="d" and len(tok_lst)>1:
				try:
					val_dst=float(tok_lst[1])
					Dev_cfg["man_dst"]=True
					Sen_dat["dist_cm"]=val_dst
					log_inf(f"Simulated distance manually set to {val_dst:.1f} cm")
					chk_alt()
				except ValueError:
					print("Invalid distance parameter")
			elif cmd_op=="b" and len(tok_lst)>1:
				try:
					val_bat=float(tok_lst[1])
					Sen_dat["bat_pct"]=val_bat
					log_inf(f"Simulated battery manually set to {val_bat:.1f}%")
				except ValueError:
					print("Invalid battery parameter")
			elif cmd_op=="t" and len(tok_lst)>1:
				try:
					val_tmp=float(tok_lst[1])
					Sen_dat["temp_c"]=val_tmp
					log_inf(f"Simulated temperature manually set to {val_tmp:.1f} C")
				except ValueError:
					print("Invalid temperature parameter")
			elif cmd_op=="reboot":
				asyncio.create_task(hdl_cmd(json.dumps({"command":"REBOOT"})))
			elif cmd_op=="mute":
				asyncio.create_task(hdl_cmd(json.dumps({"command":"MUTE"})))
			elif cmd_op=="unmute":
				asyncio.create_task(hdl_cmd(json.dumps({"command":"UNMUTE"})))
			elif cmd_op=="status":
				print(f"Device: {Dev_cfg['dev_id']} | Dist: {Sen_dat['dist_cm']}cm | Bat: {Sen_dat['bat_pct']}% | Tmp: {Sen_dat['temp_c']}C | Cam: {Sen_dat['cam_on']} | Vol: {Dev_cfg['spk_vol']}")
			elif cmd_op in ("h","help"):
				print("Available commands:\n  a            Trigger instant hazard alert\n  d <cm>       Set ultrasonic distance in cm (e.g. d 25)\n  b <pct>      Set battery percentage (e.g. b 90)\n  t <c>        Set temperature celsius (e.g. t 52)\n  reboot       Simulate hardware reboot\n  mute/unmute  Toggle speaker audio\n  status       Show current sensor readings\n  q            Exit mock server")
			else:
				print(f"Unknown command: '{cmd_lin}'. Type 'h' for help.")
		except Exception as err:
			log_err(f"Console input error: {err}")
			break
def req_ext():
	global Is_run
	Is_run=False
	if Evt_lop and not Evt_lop.is_closed():
		Evt_lop.call_soon_threadsafe(Evt_lop.stop)
def sig_hdl(sig,frm):
	log_inf(f"Received termination signal ({sig}), initiating clean shutdown...")
	req_ext()
def parse_arg():
	prs=argparse.ArgumentParser(description="Raspberry Pi 4 Mock Server for PBL6 Assistive Monitor")
	prs.add_argument("--device-id",default="pi4_01",help="MQTT device ID (default: pi4_01)")
	prs.add_argument("--broker",default="broker.hivemq.com",help="MQTT broker host (default: broker.hivemq.com)")
	prs.add_argument("--port",type=int,default=1883,help="MQTT broker port (default: 1883)")
	prs.add_argument("--camera-index",type=int,default=0,help="Webcam camera index (default: 0)")
	prs.add_argument("--synthetic",action="store_true",help="Force synthetic radar HUD video feed")
	prs.add_argument("--headless",action="store_true",help="Disable interactive console input")
	prs.add_argument("--interval",type=float,default=3.0,help="Telemetry publication interval in seconds (default: 3.0)")
	return prs.parse_args()
async def run_srv():
	global Vid_trk,Aud_snk,Cli_mq,Evt_lop
	Evt_lop=asyncio.get_running_loop()
	Vid_trk=PiVidTrk(cam_idx=Dev_cfg["cam_idx"],syn_mod=Dev_cfg["syn_mod"])
	Aud_snk=AudSnk()
	cid=f"{Dev_cfg['dev_id']}_mock_{int(time.time()*1000)%100000}"
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
	tsk_lst=[asyncio.create_task(tel_lop(interval=Dev_cfg["tel_int"]))]
	if not Dev_cfg["hed_mod"]:
		tsk_lst.append(asyncio.create_task(cli_lop()))
	try:
		while Is_run:
			await asyncio.sleep(0.5)
	except asyncio.CancelledError:
		pass
	finally:
		log_inf("Shutting down mock server components...")
		for cur_tsk in tsk_lst:
			cur_tsk.cancel()
		now_ts=int(time.time())
		Cli_mq.publish(f"pbl6/{dev_id}/status",json.dumps({"status":"offline","timestamp":now_ts}),qos=1,retain=True)
		for cur_pc in list(Pc_set):
			try:
				await cur_pc.close()
			except Exception:
				pass
		Pc_set.clear()
		Vid_trk.close()
		Aud_snk.close()
		Cli_mq.loop_stop()
		Cli_mq.disconnect()
		log_inf("Mock Pi Server stopped cleanly.")
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
	Dev_cfg["syn_mod"]=arg_obj.synthetic
	Dev_cfg["hed_mod"]=arg_obj.headless
	Dev_cfg["tel_int"]=arg_obj.interval
	try:
		asyncio.run(run_srv())
	except (KeyboardInterrupt,SystemExit):
		pass
if __name__=="__main__":
	main()

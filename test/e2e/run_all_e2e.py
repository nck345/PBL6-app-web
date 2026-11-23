import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_harness import E2EResultCollector

def main():
	parser = argparse.ArgumentParser(description="PBL6 E2E Test Suite Runner")
	parser.add_argument(
		"--tier",
		choices=["1", "2", "3", "4", "all"],
		default="all",
		help="Filter execution to specific test tier (default: all)"
	)
	parser.add_argument(
		"--broker",
		default="127.0.0.1",
		help="MQTT broker host (default: 127.0.0.1 for embedded)"
	)
	parser.add_argument(
		"--port",
		type=int,
		default=1883,
		help="MQTT broker port (default: 1883)"
	)
	parser.add_argument(
		"--device-id",
		default="pi4_01",
		help="Device ID (default: pi4_01)"
	)
	parser.add_argument(
		"--output",
		default="test/e2e/e2e_results.json",
		help="Output path for structured JSON results report"
	)
	parser.add_argument(
		"-v", "--verbose",
		action="store_true",
		help="Enable verbose output"
	)

	args = parser.parse_args()

	base_dir = os.path.dirname(os.path.abspath(__file__))
	tier_files = {
		"1": [os.path.join(base_dir, "tier1_feature_tests.py")],
		"2": [os.path.join(base_dir, "tier2_boundary_tests.py")],
		"3": [os.path.join(base_dir, "tier3_pairwise_tests.py")],
		"4": [os.path.join(base_dir, "tier4_scenario_tests.py")]
	}

	selected_files = []
	if args.tier == "all":
		selected_files = (
			tier_files["1"] +
			tier_files["2"] +
			tier_files["3"] +
			tier_files["4"]
		)
	else:
		selected_files = tier_files[args.tier]

	import pytest
	collector = E2EResultCollector()
	collector.reset()

	pytest_args = list(selected_files)
	if args.verbose:
		pytest_args.append("-v")
	else:
		pytest_args.append("-q")

	print("\n" + "=" * 70)
	print(f"Starting PBL6 E2E Test Suite (Tier: {args.tier.upper()})")
	print(f"Targeting files: {[os.path.basename(f) for f in selected_files]}")
	print("=" * 70)

	t_start = time.perf_counter()
	exit_code = pytest.main(pytest_args)
	total_elapsed = time.perf_counter() - t_start

	output_path = os.path.abspath(args.output)
	collector.export_json(output_path)

	print("\n")
	collector.print_summary_table()
	print(f"Total Suite Runtime: {total_elapsed:.2f} seconds")
	print(f"Structured Report Exported: {output_path}")

	summary = collector.get_summary()
	if args.tier == "all":
		expected_total = 256
		if summary["total_tests"] != expected_total:
			print(f"\n[ERROR] Expected {expected_total} tests, but ran {summary['total_tests']}!")
			sys.exit(1)

	if exit_code == 0 and summary["failed"] == 0:
		print("\n[SUCCESS] 100% of E2E test cases passed successfully.")
		sys.exit(0)
	else:
		print(f"\n[FAILURE] {summary['failed']} test case(s) failed.")
		sys.exit(1)

if __name__ == "__main__":
	main()

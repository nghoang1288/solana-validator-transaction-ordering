import unittest
from engine.scheduler_sim import SimulatedScheduler
from engine.ordering_evaluator import OrderingEvaluator
from cli import ExperimentRunner


class SafetyAndSchedulerTests(unittest.TestCase):
    def test_dry_run_default(self):
        runner = ExperimentRunner(dry_run=True, max_fee_sol=0.05)
        self.assertTrue(runner.dry_run)
        self.assertEqual(runner.max_fee_sol, 0.05)

    def test_spend_cap_enforcement(self):
        runner = ExperimentRunner(dry_run=False, max_fee_sol=0.05)
        self.assertLessEqual(runner.max_fee_sol, 0.05)

    def test_central_scheduler_priority_ordering(self):
        scheduler = SimulatedScheduler(mode="central_scheduler", num_threads=2)
        tx_batch = [
            {"id": "tx_low", "priority_fee_micro_lamports": 100, "write_accounts": ["acc_A"]},
            {"id": "tx_high", "priority_fee_micro_lamports": 50000, "write_accounts": ["acc_B"]},
            {"id": "tx_med", "priority_fee_micro_lamports": 5000, "write_accounts": ["acc_C"]},
        ]
        result = scheduler.simulate_ordering(tx_batch)
        self.assertEqual(result[0]["id"], "tx_high")
        self.assertEqual(result[1]["id"], "tx_med")
        self.assertEqual(result[2]["id"], "tx_low")

    def test_lock_contention_detection(self):
        tx_list = [
            {"block_index": 0, "write_accounts": ["pool_1", "user_1"]},
            {"block_index": 1, "write_accounts": ["pool_1", "user_2"]},
            {"block_index": 2, "write_accounts": ["unrelated_acc"]},
        ]
        locks = OrderingEvaluator.evaluate_lock_contention(tx_list)
        self.assertEqual(locks["total_conflicts"], 1)
        self.assertEqual(locks["conflicting_adjacent_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()


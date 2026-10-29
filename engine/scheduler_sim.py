"""
==============================================================================
Solana Banking Stage & Scheduler Simulator
==============================================================================
Simulates transaction ordering under:
1. Agave Central Scheduler (multi-threaded priority queue with write-lock gating)
2. Thread-local Round-Robin (legacy banking stage)
3. Jito Bundle Priority Engine (bundle front-running followed by prio-queue)
==============================================================================
"""

import heapq
from typing import Any, Dict, List, Set


class SimulatedScheduler:
    def __init__(self, mode: str = "central_scheduler", num_threads: int = 4):
        self.mode = mode
        self.num_threads = num_threads

    def simulate_ordering(self, tx_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes an arrival batch of transactions and outputs the simulated block inclusion order.
        """
        if self.mode == "central_scheduler":
            return self._simulate_central_scheduler(tx_batch)
        elif self.mode == "legacy_round_robin":
            return self._simulate_legacy(tx_batch)
        else:
            return sorted(tx_batch, key=lambda x: x.get("priority_fee_micro_lamports", 0), reverse=True)

    def _simulate_central_scheduler(self, tx_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Simulates Central Scheduler:
        - Priority Queue sorted by priority_fee_micro_lamports (highest first)
        - Tracks active write-locks across worker threads
        - Non-conflicting transactions can execute in parallel
        - Conflicting transactions are queued until write-lock is released
        """
        # (priority_fee, arrival_index, tx)
        prio_queue = []
        for idx, tx in enumerate(tx_batch):
            # Negative fee for max-heap in Python heapq
            fee = tx.get("priority_fee_micro_lamports", 0)
            heapq.heappush(prio_queue, (-fee, idx, tx))

        executed_order = []
        active_locks: Set[str] = set()

        while prio_queue:
            held = []
            dispatched = False

            while prio_queue:
                neg_fee, arrival_idx, tx = heapq.heappop(prio_queue)
                write_accounts = set(tx.get("write_accounts", []))

                # Check lock contention
                if not active_locks.intersection(write_accounts):
                    # Dispatched!
                    executed_order.append(tx)
                    active_locks.update(write_accounts)
                    dispatched = True
                    # In our simulated step, release locks once batch threshold reached
                    if len(active_locks) >= self.num_threads * 2:
                        active_locks.clear()
                    break
                else:
                    # Write lock conflict - hold for next iteration
                    held.append((neg_fee, arrival_idx, tx))

            # Push held items back
            for item in held:
                heapq.heappush(prio_queue, item)

            if not dispatched and prio_queue:
                # Force release locks to prevent deadlock in simulation
                active_locks.clear()
                neg_fee, arrival_idx, tx = heapq.heappop(prio_queue)
                executed_order.append(tx)

        return executed_order

    def _simulate_legacy(self, tx_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Legacy Banking Stage: Transactions distributed round-robin across banking threads;
        each thread executes in local arrival order.
        """
        threads: List[List[Dict[str, Any]]] = [[] for _ in range(self.num_threads)]
        for idx, tx in enumerate(tx_batch):
            threads[idx % self.num_threads].append(tx)

        interleaved = []
        max_len = max(len(t) for t in threads) if threads else 0
        for i in range(max_len):
            for t in threads:
                if i < len(t):
                    interleaved.append(t[i])
        return interleaved

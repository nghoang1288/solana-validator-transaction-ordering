"""
==============================================================================
Solana Validator Transaction Ordering Evaluator & Statistical Engine
==============================================================================
Measures empirical ordering behavior across blocks and validators:
- Spearman Rank Correlation between Priority Fee and Block Position
- Inversion Count & Prio-Queue Fidelity Ratio
- Non-conflicting vs Conflicting Account Serialization
- Client Software Behavioral Comparison (Agave vs Jito-Solana vs Forks)
==============================================================================
"""

import math
from typing import Any, Dict, List, Tuple


class OrderingEvaluator:
    @staticmethod
    def calculate_spearman_rank_correlation(tx_list: List[Dict[str, Any]]) -> float:
        """
        Calculates Spearman rank correlation between Priority Fee and Block Index.
        A negative value (e.g. -0.75) indicates higher priority fee lands EARLIER in the block.
        """
        n = len(tx_list)
        if n < 2:
            return 0.0

        # Extract pairs: (block_index, priority_fee)
        indices = [tx["block_index"] for tx in tx_list]
        fees = [tx["priority_fee_micro_lamports"] for tx in tx_list]

        # Rank transformations
        def get_ranks(arr: List[float]) -> List[float]:
            sorted_indices = sorted(range(len(arr)), key=lambda k: arr[k])
            ranks = [0.0] * len(arr)
            for rank, idx in enumerate(sorted_indices):
                ranks[idx] = float(rank + 1)
            return ranks

        rank_x = get_ranks(indices)
        rank_y = get_ranks(fees)

        # Covariance / Variance of ranks
        mean_x = sum(rank_x) / n
        mean_y = sum(rank_y) / n

        num = sum((rank_x[i] - mean_x) * (rank_y[i] - mean_y) for i in range(n))
        den_x = sum((rank_x[i] - mean_x) ** 2 for i in range(n))
        den_y = sum((rank_y[i] - mean_y) ** 2 for i in range(n))

        if den_x == 0 or den_y == 0:
            return 0.0

        return num / math.sqrt(den_x * den_y)

    @staticmethod
    def calculate_prio_fidelity(tx_list: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Evaluates the degree to which higher-fee transactions execute before lower-fee ones.
        Returns:
        - non_zero_fee_ratio: Percentage of transactions paying > 0 priority fee
        - fee_dominance_score: 0.0 (pure random/arrival order) to 1.0 (strict prio queue)
        """
        non_zero = [tx for tx in tx_list if tx["priority_fee_micro_lamports"] > 0]
        if not non_zero:
            return {"non_zero_fee_ratio": 0.0, "fee_dominance_score": 0.0, "spearman_corr": 0.0}

        corr = OrderingEvaluator.calculate_spearman_rank_correlation(tx_list)
        # Invert correlation so that +1.0 means high fee lands first
        fee_dominance = max(0.0, min(1.0, -corr))

        return {
            "non_zero_fee_ratio": len(non_zero) / len(tx_list),
            "fee_dominance_score": fee_dominance,
            "spearman_corr": corr,
        }

    @staticmethod
    def evaluate_lock_contention(tx_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detects whether adjacent transactions share write-locks, requiring serial execution.
        """
        conflicts = 0
        total_pairs = max(1, len(tx_list) - 1)

        for i in range(len(tx_list) - 1):
            curr_writes = set(tx_list[i].get("write_accounts", []))
            next_writes = set(tx_list[i + 1].get("write_accounts", []))
            if curr_writes.intersection(next_writes):
                conflicts += 1

        return {
            "conflicting_adjacent_ratio": conflicts / total_pairs,
            "total_conflicts": conflicts,
        }

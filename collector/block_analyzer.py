"""
==============================================================================
Solana Block Transaction Ordering & Compute Budget Analyzer
==============================================================================
Extracts raw block data via getBlock RPC:
- Block index position (order of execution)
- Compute Budget instructions (Priority Fee micro-lamports / CU)
- Write-lock conflict graph (non-conflicting vs conflicting accounts)
- Signatures and execution status
==============================================================================
"""

import base64
import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"


class BlockAnalyzer:
    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url

    def _rpc_call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        req = urllib.request.Request(
            self.rpc_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "SolanaValidatorOrderingResearch/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"RPC Error ({method}): {data['error']}")
            return data.get("result")

    def fetch_block(self, slot: int) -> Optional[Dict[str, Any]]:
        """Queries confirmed block with JSON or JSONParsed encoding."""
        params = [
            slot,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 1,
                "transactionDetails": "full",
                "rewards": False,
            },
        ]
        return self._rpc_call("getBlock", params)

    def parse_transaction_ordering(self, block: Dict[str, Any], slot: int) -> List[Dict[str, Any]]:
        """
        Parses all transactions in a block and extracts:
        - index: Position in the block (0, 1, 2, ...)
        - signature: Transaction ID
        - priority_fee_micro_lamports: SetComputeUnitPrice value
        - compute_unit_limit: SetComputeUnitLimit value
        - total_fee_lamports: Total lamports paid
        - write_accounts: List of accounts with write locks
        """
        transactions = block.get("transactions", [])
        parsed = []

        for idx, tx in enumerate(transactions):
            meta = tx.get("meta") or {}
            transaction = tx.get("transaction") or {}
            message = transaction.get("message") or {}

            signatures = transaction.get("signatures", [])
            sig = signatures[0] if signatures else "unknown"

            # Parse compute budget instructions
            cu_price = 0
            cu_limit = 200_000  # Default Solana compute budget
            write_accounts = []

            # Instructions parsing
            instructions = message.get("instructions", [])
            for ix in instructions:
                prog = ix.get("program") or ix.get("programId")
                if prog == "compute_budget" or prog == COMPUTE_BUDGET_PROGRAM_ID:
                    parsed_ix = ix.get("parsed")
                    if isinstance(parsed_ix, dict):
                        ix_type = parsed_ix.get("type")
                        info = parsed_ix.get("info", {})
                        if ix_type == "setComputeUnitPrice":
                            cu_price = int(info.get("microLamports") or 0)
                        elif ix_type == "setComputeUnitLimit":
                            cu_limit = int(info.get("units") or 200_000)

            # Account keys & write lock analysis
            account_keys = message.get("accountKeys", [])
            for acc in account_keys:
                if isinstance(acc, dict):
                    if acc.get("writable"):
                        write_accounts.append(acc.get("pubkey"))
                elif isinstance(acc, str):
                    write_accounts.append(acc)

            fee_lamports = meta.get("fee", 5000)

            parsed.append({
                "slot": slot,
                "block_index": idx,
                "signature": sig,
                "priority_fee_micro_lamports": cu_price,
                "compute_unit_limit": cu_limit,
                "total_fee_lamports": fee_lamports,
                "write_accounts": write_accounts[:10],
                "err": meta.get("err"),
            })

        return parsed

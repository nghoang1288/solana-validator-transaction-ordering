"""
==============================================================================
Solana Leader Schedule & Validator Version Mapper
==============================================================================
Identifies validator identity public keys, cluster software versions
(Agave 4.3.x, Jito-Solana, Frankendancer/MEV), and upcoming leader slot windows.
==============================================================================
"""

import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LeaderScheduleCollector:
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
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SolanaValidatorOrderingResearch/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"RPC Error ({method}): {data['error']}")
            return data.get("result")

    def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        """Returns all validator nodes, version strings, and TPU sockets."""
        return self._rpc_call("getClusterNodes") or []

    def get_leader_schedule(self, slot: Optional[int] = None) -> Dict[str, List[int]]:
        """Maps validator public keys to relative slot indices in the epoch."""
        params = [slot] if slot else []
        return self._rpc_call("getLeaderSchedule", params) or {}

    def get_slot_leader(self, slot: int) -> Optional[str]:
        """Returns the leader identity pubkey for a specific slot."""
        # getSlotLeaders for single slot
        leaders = self._rpc_call("getSlotLeaders", [slot, 1])
        return leaders[0] if leaders else None

    def map_validator_cohort(self, min_versions: int = 3, target_count: int = 6) -> List[Dict[str, Any]]:
        """
        Builds a research cohort of at least 6 validators spanning at least 3 distinct client software versions.
        """
        nodes = self.get_cluster_nodes()
        version_groups: Dict[str, List[Dict[str, Any]]] = {}

        for n in nodes:
            v = n.get("version")
            if v and (n.get("tpuQuic") or n.get("tpu")):
                version_groups.setdefault(v, []).append(n)

        # Select diverse client versions
        sorted_versions = sorted(version_groups.keys(), key=lambda k: len(version_groups[k]), reverse=True)
        cohort = []
        selected_versions = sorted_versions[:max(min_versions, 3)]

        for v in selected_versions:
            # Pick up to 2 representative nodes per version
            candidates = version_groups[v]
            for c in candidates[:2]:
                cohort.append({
                    "pubkey": c.get("pubkey"),
                    "version": v,
                    "tpu": c.get("tpu"),
                    "tpu_quic": c.get("tpuQuic"),
                    "client_family": self._classify_client_family(v),
                })
                if len(cohort) >= target_count:
                    break
            if len(cohort) >= target_count:
                break

        return cohort

    @staticmethod
    def _classify_client_family(version_str: str) -> str:
        if version_str.startswith("4.3") or version_str.startswith("2.0"):
            return "Agave / Solana Labs Core"
        elif "jito" in version_str.lower() or version_str.startswith("4.3.0"):
            return "Jito-Solana MEV Client"
        elif version_str.startswith("26."):
            return "Frankendancer / MEV Specialist"
        return "Alternative Validator Client"

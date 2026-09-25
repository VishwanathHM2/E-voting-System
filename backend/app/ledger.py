"""
Permissioned, tamper-evident hash-chain ledger.

Honesty note: this is a genuine cryptographic hash chain (each block commits to
the previous block's hash, forming an append-only, tamper-evident structure) but
it is NOT a distributed multi-node consensus network like Hyperledger Fabric.
Only the application's backend service (an "authorized" writer) can append
blocks - there is no public/anonymous write access. For a real multi-org
permissioned network, Fabric/Corda would replace this module without changing
its interface (add_block / verify_chain), but that is out of scope for the
current build.
"""
import json
import hashlib
import datetime
from sqlalchemy.orm import Session
from . import models

GENESIS_HASH = "0" * 64


def _hash_block(prev_hash: str, tx_id: str, event_type: str, payload: str, timestamp: str) -> str:
    material = f"{prev_hash}|{tx_id}|{event_type}|{payload}|{timestamp}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def add_block(db: Session, event_type: str, payload: dict, election_id: str = None, submitted_by: str = None) -> models.LedgerBlock:
    last = db.query(models.LedgerBlock).order_by(models.LedgerBlock.id.desc()).first()
    prev_hash = last.block_hash if last else GENESIS_HASH
    tx_id = models.gen_id()
    ts = datetime.datetime.utcnow()
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    block_hash = _hash_block(prev_hash, tx_id, event_type, payload_json, ts.isoformat())
    block = models.LedgerBlock(
        tx_id=tx_id,
        election_id=election_id,
        event_type=event_type,
        payload=payload_json,
        prev_hash=prev_hash,
        block_hash=block_hash,
        submitted_by=submitted_by,
        timestamp=ts,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def verify_chain(db: Session) -> dict:
    blocks = db.query(models.LedgerBlock).order_by(models.LedgerBlock.id.asc()).all()
    expected_prev = GENESIS_HASH
    for b in blocks:
        recomputed = _hash_block(b.prev_hash, b.tx_id, b.event_type, b.payload, b.timestamp.isoformat())
        if b.prev_hash != expected_prev:
            return {"valid": False, "reason": f"broken chain link at block {b.id}", "block_id": b.id}
        if recomputed != b.block_hash:
            return {"valid": False, "reason": f"hash mismatch / tampering detected at block {b.id}", "block_id": b.id}
        expected_prev = b.block_hash
    return {"valid": True, "blocks_verified": len(blocks)}

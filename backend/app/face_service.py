"""
Face recognition using OpenCV only (haar-cascade face detection + HOG
feature descriptors as the embedding). Runs fully locally, no third-party
API calls, and installs in seconds with no C++ compilation step (unlike
dlib-based `face_recognition`, which was tried first and is too slow to
build from source for a short local-dev turnaround).

This is a classical, well-established feature-based face recognition
technique (HOG descriptors), not raw pixel-difference comparison. It is
less accurate than a deep embedding model (dlib ResNet / ArcFace /
FaceNet) - an honest limitation worth stating in your report/viva.
To upgrade later: swap this module's implementation while keeping the
same function signatures (extract_embedding / matches / find_duplicate) -
nothing else in the codebase needs to change.
"""
import json
import base64
import io
import numpy as np
import cv2
from PIL import Image

from .config import settings

_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

_FACE_SIZE = (128, 128)
_hog = cv2.HOGDescriptor(_winSize=_FACE_SIZE, _blockSize=(32, 32), _blockStride=(16, 16),
                          _cellSize=(16, 16), _nbins=9)


def _decode_image(image_b64: str) -> np.ndarray:
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]
    raw = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.array(img)


def extract_embedding(image_b64: str) -> dict:
    img = _decode_image(image_b64)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(60, 60))

    if len(faces) == 0:
        return {"ok": False, "reason": "no_face_detected"}
    if len(faces) > 1:
        return {"ok": False, "reason": "multiple_faces_detected"}

    (x, y, w, h) = faces[0]
    face_region = gray[y:y + h, x:x + w]
    face_region = cv2.resize(face_region, _FACE_SIZE)
    face_region = cv2.equalizeHist(face_region)

    descriptor = _hog.compute(face_region)
    if descriptor is None or descriptor.size == 0:
        return {"ok": False, "reason": "embedding_extraction_failed"}

    vec = descriptor.flatten()
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return {"ok": True, "embedding": vec.tolist()}


def average_embeddings(embeddings: list) -> list:
    arr = np.array(embeddings)
    avg = arr.mean(axis=0)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg.tolist()


def distance(embedding_a: list, embedding_b: list) -> float:
    a = np.array(embedding_a)
    b = np.array(embedding_b)
    return float(np.linalg.norm(a - b))


def matches(embedding_a: list, embedding_b: list, threshold: float = None) -> bool:
    threshold = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD
    return distance(embedding_a, embedding_b) <= threshold


def find_duplicate(new_embedding: list, existing: list, threshold: float = None) -> dict:
    threshold = threshold if threshold is not None else settings.FACE_DUP_THRESHOLD
    best = None
    for voter_id, emb_json in existing:
        emb = json.loads(emb_json)
        d = distance(new_embedding, emb)
        if best is None or d < best[1]:
            best = (voter_id, d)
    if best and best[1] <= threshold:
        return {"duplicate": True, "matched_voter_id": best[0], "distance": best[1]}
    return {"duplicate": False}

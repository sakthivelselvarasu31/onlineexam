import base64
import os
from typing import Dict, Any, Tuple, Optional

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None



class FaceDetector:
    def __init__(self, cascade_path: Optional[str] = None):
        self.cascade = None
        self.enabled = False
        self._init_cascade(cascade_path)

    def _init_cascade(self, cascade_path: Optional[str] = None):
        if cv2 is None or np is None:
            self.enabled = False
            return

        if not hasattr(cv2, 'CascadeClassifier'):
            self.enabled = False
            return

        resolved_path = cascade_path
        if not resolved_path:
            haar_dir = getattr(cv2.data, 'haarcascades', None)
            if haar_dir:
                resolved_path = os.path.join(haar_dir, 'haarcascade_frontalface_default.xml')

        if resolved_path and os.path.exists(resolved_path):
            try:
                cascade = cv2.CascadeClassifier(resolved_path)
                if hasattr(cascade, 'empty') and not cascade.empty():
                    self.cascade = cascade
                    self.enabled = True
            except Exception:
                self.cascade = None
                self.enabled = False

    def decode_image(self, image_data_uri: str) -> Optional[Any]:
        """Decodes base64 Data URI into BGR cv2 image array."""
        if cv2 is None or np is None or not image_data_uri:
            return None
        if not isinstance(image_data_uri, str) or not image_data_uri.startswith('data:image'):
            return None

        try:
            header, encoded = image_data_uri.split(',', 1)
            image_bytes = base64.b64decode(encoded)
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def detect_faces(self, img: Any, scale_factor: float = 1.1, min_neighbors: int = 5) -> Dict[str, Any]:
        """
        Detects faces in OpenCV image frame.
        Returns dictionary with detection results.
        """
        if img is None:
            return {
                'face_present': False,
                'face_count': 0,
                'is_multi_face': False,
                'bounding_boxes': [],
                'status': 'invalid_image',
            }

        if not self.enabled or self.cascade is None:
            # Fallback when OpenCV cascade is unavailable
            return {
                'face_present': True,
                'face_count': 1,
                'is_multi_face': False,
                'bounding_boxes': [],
                'status': 'fallback_enabled',
            }

        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Equalize histogram for lighting variation robustness
            gray = cv2.equalizeHist(gray)

            faces = self.cascade.detectMultiScale(
                gray,
                scaleFactor=scale_factor,
                minNeighbors=min_neighbors,
                minSize=(30, 30),
            )

            boxes = []
            for (x, y, w, h) in faces:
                boxes.append({'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)})

            face_count = len(boxes)
            return {
                'face_present': face_count > 0,
                'face_count': face_count,
                'is_multi_face': face_count > 1,
                'bounding_boxes': boxes,
                'status': 'success',
            }
        except Exception as e:
            return {
                'face_present': False,
                'face_count': 0,
                'is_multi_face': False,
                'bounding_boxes': [],
                'status': f'error: {str(e)}',
            }


# Singleton face detector instance
face_detector_instance = FaceDetector()

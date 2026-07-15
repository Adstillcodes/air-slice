"""MediaPipe hand tracking: one hand, index fingertip only (the "blade")."""

import cv2
import mediapipe as mp

INDEX_FINGERTIP = 8


class HandTracker:
    def __init__(self):
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,  # fastest model — plenty for a fingertip
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def fingertip(self, bgr_frame):
        """Return (x, y) of the index fingertip in normalized [0,1] coords, or None."""
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        result = self._hands.process(rgb)
        if not result.multi_hand_landmarks:
            return None
        lm = result.multi_hand_landmarks[0].landmark[INDEX_FINGERTIP]
        return (min(max(lm.x, 0.0), 1.0), min(max(lm.y, 0.0), 1.0))

    def close(self):
        self._hands.close()

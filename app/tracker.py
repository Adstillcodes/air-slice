"""MediaPipe hand tracking: one hand, index fingertip only (the "blade")."""

import cv2
import mediapipe as mp

INDEX_FINGERTIP = 8


class HandTracker:
    def __init__(self):
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=3,
            model_complexity=0,  # fastest model — plenty for a fingertip
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._face = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )

    def process(self, bgr_frame):
        """Return finger (x,y), list of face rects, and hand area."""
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        
        finger_pos = None
        max_area = 0.0
        hand_result = self._hands.process(rgb)
        if hand_result.multi_hand_landmarks:
            closest_hand = None
            max_area = -1
            
            for hand_landmarks in hand_result.multi_hand_landmarks:
                xs = [lm.x for lm in hand_landmarks.landmark]
                ys = [lm.y for lm in hand_landmarks.landmark]
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                if area > max_area:
                    max_area = area
                    closest_hand = hand_landmarks
                    
            if closest_hand:
                lm = closest_hand.landmark[INDEX_FINGERTIP]
                finger_pos = (min(max(lm.x, 0.0), 1.0), min(max(lm.y, 0.0), 1.0))
            
        faces = []
        face_result = self._face.process(rgb)
        if face_result.detections:
            for d in face_result.detections:
                bbox = d.location_data.relative_bounding_box
                faces.append((
                    min(max(bbox.xmin, 0.0), 1.0),
                    min(max(bbox.ymin, 0.0), 1.0),
                    min(max(bbox.width, 0.0), 1.0),
                    min(max(bbox.height, 0.0), 1.0)
                ))
                
        return finger_pos, faces, max_area

    def close(self):
        self._hands.close()
        self._face.close()

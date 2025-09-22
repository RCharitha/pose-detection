import mediapipe as mp
from utils.angle_utils import calculate_angle
import time

mp_pose = mp.solutions.pose

# Shared variables (reps, feedback, etc.) for thread-safe usage (simplified for demo)
import time

class ExerciseState:
    def __init__(self):
        self.reps = 0
        self.direction = None
        self.feedback = "Start position"
        self.feedback_class = "neutral"
        self.current_time = 0
        self.start_time = None
        self.is_exercising = False  # Track if user is actively exercising
        self.last_update_time = time.time()
        self.prev_angle = None
        self.prev_arm_angle = None
        self.prev_left_angle = None
        self.perfect_time = 0
    
    def update_time(self, is_active):
        """Update the exercise duration timer only when actively exercising"""
        current_time = time.time()
        
        if self.start_time is None:
            self.start_time = current_time
        
        # Only count time when actively exercising
        if is_active:
            if not self.is_exercising:
                # Just started exercising
                self.is_exercising = True
                self.last_update_time = current_time
            else:
                # Continue counting exercise time
                elapsed = current_time - self.last_update_time
                self.current_time += elapsed
                self.last_update_time = current_time
        else:
            # Not actively exercising
            self.is_exercising = False
        
        return self
    
    def reset(self):
        """Reset all state variables"""
        self.__init__()
# ===== EXERCISE LOGIC FUNCTIONS =====
# Each function takes (landmarks, state) and returns updated state.
def squat_logic(landmarks, state):
    hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    knee = landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value]
    ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value]
    
    angle = calculate_angle(hip, knee, ankle)
    
    # Detect if user is actively exercising (knee bent - not standing straight)
    is_active = angle < 160  # Considered active when not standing straight
    
    # Update time only when active
    state.update_time(is_active)
    
    # Initialize prev_angle if None
    if state.prev_angle is None:
        state.prev_angle = angle
    
    # Squat rules
    if angle > 160:
        state.direction = "down"
        state.feedback = "Stand straight. Ready to squat!"
        state.feedback_class = "neutral"
    
    elif 130 < angle <= 160:
        state.feedback = "Start lowering (aim for 90°)"
        state.feedback_class = "warning"
    
    elif 80 <= angle <= 100:  # Ideal squat range
        if state.direction == "down":
            state.feedback = "Perfect depth! Push up now."
            state.feedback_class = "correct"
        else:
            state.feedback = "Good form! Return to start."
            state.feedback_class = "correct"
    
    elif angle < 80:  # Too deep
        state.feedback = "Too deep! Raise slightly."
        state.feedback_class = "error"
    
    else:  # Partial squat
        state.feedback = "Go deeper! Aim for 90°."
        state.feedback_class = "warning"
    
    # Count reps only when returning to standing after a good squat
    if (angle > 160 and state.direction == "down" and 
        state.prev_angle is not None and 80 <= state.prev_angle <= 100):
        state.reps += 1
        state.direction = "up"
    
    state.prev_angle = angle  # Store for next frame
    return state



def pushup_logic(landmarks, state):
    # Key landmarks (using left side; mirror for right)
    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
    wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
    hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    
    # Calculate angles
    arm_angle = calculate_angle(shoulder, elbow, wrist)  # Elbow bend
    body_angle = calculate_angle(shoulder, hip, wrist)   # Body alignment
    
    # Detect if user is actively exercising (elbow bent - not at top position)
    is_active = arm_angle < 160  # Considered active when not at top position
    
    # Update time only when active
    state.update_time(is_active)
    
    # Push-up rules
    if arm_angle > 160:
        state.direction = "down"
        state.feedback = "Ready to lower (keep body straight!)"
        state.feedback_class = "neutral"
    
    elif 90 <= arm_angle <= 120:  # Ideal lowering phase
        if body_angle > 160:  # Body straight
            state.feedback = "Lower slowly (good form!)"
            state.feedback_class = "correct"
        else:  # Sagging hips/arched back
            state.feedback = "Keep body straight! Engage core."
            state.feedback_class = "warning"
    
    elif arm_angle < 90:  # Push-up depth
        if body_angle > 160:
            state.feedback = "Perfect depth! Push up now."
            state.feedback_class = "correct"
        else:
            state.feedback = "Fix posture before pushing up!"
            state.feedback_class = "error"
    
    # Count reps only when returning to top with good form
    if arm_angle > 160 and state.direction == "up" and state.prev_arm_angle < 90:
        if body_angle > 160:  # Only count if body was straight
            state.reps += 1
        else:
            state.feedback = "Rep discarded! Keep body straight."
            state.feedback_class = "error"
    
    # Update state
    state.prev_arm_angle = arm_angle
    state.direction = "up" if arm_angle > 140 else "down"
    return state





def plank_logic(landmarks, state):
    # Key landmarks (mid-shoulder, hip, and ankle for alignment)
    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value]
    elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
    
    # Calculate alignment angles
    body_angle = calculate_angle(shoulder, hip, ankle)  # Straight-line target: ~180°
    hip_shoulder_dist = abs(hip.y - shoulder.y)         # Vertical alignment
    
    # For plank, consider active when in reasonable position (not standing)
    # A body angle significantly different from standing (which would be close to 180°)
    # and elbow position indicating a plank position
    is_plank_position = (body_angle < 170 or body_angle > 190) and elbow.y > hip.y
    is_active = is_plank_position
    
    # Update time only when active
    state.update_time(is_active)
    
    # Plank rules
    if 170 <= body_angle <= 190:  # Ideal straight line (±10° tolerance)
        state.feedback = "Perfect plank! Hold steady."
        state.feedback_class = "correct"
    elif body_angle < 170:  # Hips too high (pike)
        state.feedback = "Hips too high! Lower them."
        state.feedback_class = "warning"
    else:  # Hips too low (sagging)
        state.feedback = "Hips sagging! Lift them."
        state.feedback_class = "error"
    
    # Elbow alignment check (optional)
    if elbow.x > shoulder.x + 0.05:  # Elbows too far forward
        state.feedback = "Elbows under shoulders!"
        state.feedback_class = "error"
    
    # Track time in perfect form
    if state.feedback_class == "correct":
        state.perfect_time += 1/30  # Assuming 30fps; adjust as needed
    else:
        state.perfect_time = max(0, state.perfect_time - 1/30)  # Penalize breaks
    
    return state






def bicep_curl_logic(landmarks, state):
    # Key landmarks (left side)
    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    elbow    = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
    wrist    = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]

    # Calculate angle at the elbow (main focus for curls)
    elbow_angle = calculate_angle(shoulder, elbow, wrist)
    
    # Detect if user is actively exercising (elbow bent between 30-160 degrees)
    is_active = 30 < elbow_angle < 160
    
    # Update time only when active
    state.update_time(is_active)

    # ---------------- Bicep Curl Rules ---------------- #

    # Case A: Arm straight (start position)
    if elbow_angle > 160:
        state.direction = "up"
        state.feedback = "Start curling! Keep elbow fixed."
        state.feedback_class = "neutral"

    # Case B: Curling range (30°–160°)
    elif 30 < elbow_angle <= 160:
        if state.direction == "up":
            state.feedback = "Curling up... Keep elbow still!"
            state.feedback_class = "correct"
        else:
            state.feedback = "Lower slowly. Control the weight."
            state.feedback_class = "correct"

    # Case C: Fully contracted (≤30°)
    elif elbow_angle <= 30:
        state.feedback = "Hold and tighten your bicep at the top of the curl before lowering."
        state.feedback_class = "correct"
        if state.direction == "up":
            state.direction = "down"

    # ---------------- Rep Counting ---------------- #
    if elbow_angle > 160 and state.direction == "down" and state.prev_angle <= 30:
        state.reps += 1

    # Save current angle for next frame
    state.prev_angle = elbow_angle
    return state






def lunge_logic(landmarks, state):
    # Key landmarks (both legs)
    left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    left_knee = landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value]
    left_ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value]
    right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value]
    right_knee = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value]
    right_ankle = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value]
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value] 
    
    # Calculate angles
    left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)  # Front leg
    right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)  # Back leg
    torso_angle = calculate_angle(left_shoulder, left_hip, left_knee)  # Torso alignment
    
    # Detect if user is actively exercising (in lunge position)
    is_active = left_knee_angle < 160 or right_knee_angle < 160  # Knees bent
    
    # Update time only when active
    state.update_time(is_active)
    
    # Lunge Rules
    if left_knee_angle > 160 and right_knee_angle > 160:  # Standing
        state.feedback = "Step forward into lunge"
        state.feedback_class = "neutral"
    
    elif left_knee_angle < 90 and right_knee_angle < 90:  # Deep lunge
        state.feedback = "Too deep! Keep front knee above ankle"
        state.feedback_class = "error"
    
    elif 90 <= left_knee_angle <= 110 and right_knee_angle > 135:  # Ideal lunge
        if torso_angle < 170:  # Leaning forward
            state.feedback = "Keep torso upright!"
            state.feedback_class = "warning"
        else:
            state.feedback = "Perfect lunge! Push through front heel"
            state.feedback_class = "correct"
            if state.direction == "down":
                state.direction = "up"
                state.reps += 1  # Count rep when returning up
    
    elif left_knee_angle > 110:  # Shallow lunge
        state.feedback = "Deeper lunge! Front knee at 90°"
        state.feedback_class = "warning"
    
    # Knee safety check
    if left_knee.x < left_ankle.x:  # Knee past toes
        state.feedback = "Front knee behind toes!"
        state.feedback_class = "error"
    
    state.prev_left_angle = left_knee_angle
    return state


# ===== EXERCISE MAPPING =====
# Map exercise names to their logic functions
EXERCISE_FUNCTIONS = {
    "squat": squat_logic,
  
    "pushup": pushup_logic,
  
    "plank": plank_logic,
    "bicep_curl": bicep_curl_logic,

    "lunges": lunge_logic
}

def get_exercise_function(exercise_name):
    """Returns the appropriate logic function for the exercise."""
    return EXERCISE_FUNCTIONS.get(exercise_name.lower())
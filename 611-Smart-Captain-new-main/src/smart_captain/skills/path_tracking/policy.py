from smart_captain.skills.path_tracking.mpc_controller import AUV_MPC
from smart_captain.skills.path_tracking.config import MPC_CONFIG


class MPCPathTrackingPolicy:
    def __init__(self, config=None):
        self.controller = AUV_MPC(config or MPC_CONFIG)

    def predict(self, observation, state=None, deterministic=True):
        action = self.controller.predict(observation)
        return action, state
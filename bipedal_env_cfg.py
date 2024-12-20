# Copyright (c) 2022-2024, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from omni.isaac.lab.managers import RewardTermCfg as RewTerm
from omni.isaac.lab.managers import SceneEntityCfg
from omni.isaac.lab.utils import configclass

import omni.isaac.lab_tasks.manager_based.locomotion.velocity.mdp as mdp
from omni.isaac.lab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    LocomotionVelocityRoughEnvCfg,
    RewardsCfg,
)

##
# Pre-defined configs
##
from omni.isaac.lab_assets import UNITREE_GO2_CFG  # isort: skip


@configclass
class Go2BipedalRewards(RewardsCfg):
    """Reward terms for the MDP."""

    termination_penalty = RewTerm(func=mdp.is_terminated, weight=-200.0)
    lin_vel_z_l2 = None
    track_lin_vel_xy_exp = RewTerm(
        func=mdp.track_lin_vel_xy_yaw_frame_exp,
        weight=1.0,
        params={"command_name": "base_velocity", "std": 0.5},
    )
    track_ang_vel_z_exp = RewTerm(
        func=mdp.track_ang_vel_z_world_exp, weight=1.0, params={"command_name": "base_velocity", "std": 0.5}
    )
    feet_air_time = RewTerm(
        func=mdp.feet_air_time_positive_biped,  # Using biped air time function
        weight=0.25,
        params={
            "command_name": "base_velocity",
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_calf"),  # Changed to calf for Go2
            "threshold": 0.4,
        },
    )
    feet_slide = RewTerm(
        func=mdp.feet_slide,
        weight=-0.25,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_calf"),  # Changed to calf for Go2
            "asset_cfg": SceneEntityCfg("robot", body_names=".*_calf"),
        },
    )
    # Penalize joint limits
    dof_pos_limits = RewTerm(
        func=mdp.joint_pos_limits, weight=-1.0, params={"asset_cfg": SceneEntityCfg("robot", joint_names=".*_calf_joint")}
    )


@configclass
class Go2BipedalEnvCfg(LocomotionVelocityRoughEnvCfg):
    rewards: Go2BipedalRewards = Go2BipedalRewards()

    def __post_init__(self):
        # post init of parent
        super().__post_init__()
        # Scene
        self.scene.robot = UNITREE_GO2_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")
        
        # Modify initial state for bipedal stance
        self.scene.robot.init_state.pos = (0.0, 0.0, 0.6)  # Increased height for standing
        self.scene.robot.init_state.joint_pos = {
            # Front legs (used for bipedal walking)
            "FL_hip_joint": 0.0,
            "FR_hip_joint": 0.0,
            "FL_thigh_joint": -0.8,  # Bent forward
            "FR_thigh_joint": -0.8,
            "FL_calf_joint": -1.5,    # Bent backward within limits
            "FR_calf_joint": -1.5,
            # Back legs (tucked up)
            "RL_hip_joint": 0.0,
            "RR_hip_joint": 0.0,
            "RL_thigh_joint": 1.6,   # Tucked up
            "RR_thigh_joint": 1.6,
            "RL_calf_joint": -2.0,   # Tucked up
            "RR_calf_joint": -2.0,
        }

        if self.scene.height_scanner:
            self.scene.height_scanner.prim_path = "{ENV_REGEX_NS}/Robot/base"

        # Randomization
        self.events.push_robot = None
        self.events.add_base_mass = None
        self.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
        self.events.base_external_force_torque.params["asset_cfg"].body_names = ["base"]
        self.events.reset_base.params = {
            "pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)},
            "velocity_range": {
                "x": (0.0, 0.0),
                "y": (0.0, 0.0),
                "z": (0.0, 0.0),
                "roll": (0.0, 0.0),
                "pitch": (0.0, 0.0),
                "yaw": (0.0, 0.0),
            },
        }

        # Terminations
        self.terminations.base_contact.params["sensor_cfg"].body_names = ["base"]

        # Rewards
        self.rewards.undesired_contacts = None
        self.rewards.flat_orientation_l2.weight = -1.0
        self.rewards.dof_torques_l2.weight = -0.001
        self.rewards.action_rate_l2.weight = -0.005
        self.rewards.dof_acc_l2.weight = -1.25e-7

        # Commands - Reduced ranges for bipedal walking
        self.commands.base_velocity.ranges.lin_vel_x = (0.0, 0.5)  # Reduced forward velocity
        self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)  # No lateral movement
        self.commands.base_velocity.ranges.ang_vel_z = (-0.5, 0.5)  # Reduced turning


@configclass
class Go2BipedalEnvCfg_PLAY(Go2BipedalEnvCfg):
    def __post_init__(self):
        # post init of parent
        super().__post_init__()

        # make a smaller scene for play
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.episode_length_s = 40.0
        # spawn the robot randomly in the grid (instead of their terrain levels)
        self.scene.terrain.max_init_terrain_level = None
        # reduce the number of terrains to save memory
        if self.scene.terrain.terrain_generator is not None:
            self.scene.terrain.terrain_generator.num_rows = 5
            self.scene.terrain.terrain_generator.num_cols = 5
            self.scene.terrain.terrain_generator.curriculum = False

        self.commands.base_velocity.ranges.lin_vel_x = (0.3, 0.3)
        self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)
        self.commands.base_velocity.ranges.ang_vel_z = (0.0, 0.0)
        self.commands.base_velocity.ranges.heading = (0.0, 0.0)
        # disable randomization for play
        self.observations.policy.enable_corruption = False
        # remove random pushing
        self.events.base_external_force_torque = None
        self.events.push_robot = None


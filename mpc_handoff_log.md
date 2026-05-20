# MPC Integration Handoff Log

Date: 2026-05-20  
Workspace: `F:\smartcaptain`

## Background

This handoff summarizes the discussion and investigation around integrating the MPC code from:

```text
HoloOcean-2.0.1/
```

into the restructured Smart Captain project:

```text
611-Smart-Captain-new-main/
```

No integration code has been written yet in this handoff. The current work was analysis, explanation, dependency repair, and integration planning.

## Smart Captain Architecture Summary

The new project is organized as a layered control framework:

```text
Natural-language command
-> LLM / heuristic task decomposition
-> TaskGraph
-> Orchestration dispatcher
-> Skill execution
-> Simulation / HoloOcean
-> Feedback / evaluator / recovery
```

Important directories:

```text
src/smart_captain/app/
```

Application entrypoints and runtime adapters. `mission_runner.py` is the high-level entrypoint.

```text
src/smart_captain/llm/
```

Natural-language command parsing and structured task decomposition.

```text
src/smart_captain/orchestration/
```

Task graph, dispatcher, feedback contracts, evaluator registry, and recovery decisions.

```text
src/smart_captain/skills/
```

Executable task capabilities. Currently `navigation` and `obstacle_avoidance` are the most complete. `search`, `mapping`, and `target_tracking` are placeholders.

```text
src/smart_captain/simulation/
```

HoloOcean environment wrapper, action mapping, sensor processing, scenario registry, and compatibility environment.

```text
src/smart_captain/rl/
```

RL model loading and multi-skill policy switching.

Current execution is still partly compatibility-based: the new task graph is bridged into legacy integer `mode` switching and runs with shared HoloOcean AUV state.

## MPC Source Files

The original MPC code lives in:

```text
HoloOcean-2.0.1/MPC/
```

Main files:

```text
MPC/mpc_controller.py
MPC/mpc_predictor.py
```

Related environment:

```text
task/task3.py
```

Related test scripts:

```text
test2.py
test3.py
```

## What `mpc_controller.py` Does

`MPC/mpc_controller.py` defines:

```python
class AUV_MPC
```

It is a CasADi + IPOPT model predictive controller.

Input:

```text
current_state + future reference states
```

State format, 12 dimensions:

```text
[x, y, z, phi, theta, psi, u, v, w, p, q, r]
```

Meaning:

```text
position: x, y, z
Euler attitude: roll phi, pitch theta, yaw psi
linear velocity: u, v, w
angular velocity: p, q, r
```

Output action, 4 dimensions:

```text
[surge, sway, heave, yaw]
```

The controller builds:

- A simplified AUV dynamics model.
- Restoring force and torque from buoyancy and gravity.
- Linear and angular damping.
- 8-thruster allocation matrix.
- Effective 4-control allocation matrix.
- MPC optimization problem over horizon `N`.

The optimization cost includes:

- State tracking error with `Q`.
- Control effort with `R`.
- Control increment smoothness with `Rd`.
- Terminal state tracking error.

The constraints include:

- Initial state equality.
- Dynamics equality constraints.
- Control lower and upper bounds.

Important method:

```python
predict(state)
```

It parses the current state and reference trajectory, solves the MPC problem, stores the optimal sequence, and returns the first 4-dimensional action.

## What `mpc_predictor.py` Does

`MPC/mpc_predictor.py` defines:

```python
class HoveringAUVModel
```

This is a NumPy version of the AUV dynamics predictor.

It does not solve an optimization problem. It predicts one next state from:

```text
current state + 8-dimensional thruster command
```

It is useful for comparing the MPC internal dynamics model against real HoloOcean simulation output.

## What `task3.py` Does

`HoloOcean-2.0.1/task/task3.py` defines:

```python
class Path_Tracing(BaseEnvironment)
```

It is the MPC path-tracking environment adapter. It does not implement MPC optimization itself. Instead, it generates the MPC input observation:

```text
current 12D AUV state + future (N+1) x 12D reference states
```

With the current config:

```text
N = 50
observation size = 12 + 51 * 12 = 624
```

It inherits from:

```python
BaseEnvironment
```

Therefore it does run inside HoloOcean. Its `step()` calls:

```python
super().step(action)
```

which sends the converted command to:

```python
self.AUV.step(command)
```

The normal MPC loop is:

```text
Path_Tracing.reset()
-> observation
-> AUV_MPC.predict(observation)
-> Path_Tracing.step(action)
-> new observation
-> repeat
```

## Path-Tracking Modes in `task3.py`

The two modes mentioned in comments are about where the reference path comes from.

### Test Mode

The environment generates a path itself. Existing path generators:

```python
_generate_random_fourier_path()
_generate_straight_path()
_generate_circular_path()
```

Current `reset()` defaults to:

```python
_generate_circular_path()
```

This means the AUV tracks a circular path around the goal point. This mode is mainly for testing the MPC path-tracking behavior.

### Execution Mode

External path points are supplied as `path_steps`.

The function:

```python
_path_from_steps(steps, current_pos)
```

turns discrete waypoints into a continuous cubic-spline path using `CubicSpline`.

This is the mode that should eventually connect to Smart Captain planning:

```text
LLM / planner outputs waypoints
-> path_tracking skill receives path_steps
-> PathTrackingEnv converts them to reference trajectory
-> MPC tracks the trajectory
```

## How to Run MPC Standalone

To see the full MPC path-tracking effect:

```powershell
cd F:\smartcaptain\HoloOcean-2.0.1
python test3.py
```

`test3.py` runs:

```text
Path_Tracing environment
-> AUV_MPC
-> HoloOcean simulation
-> trajectory logging
-> 3D plot of reference path vs actual path
```

To compare one-step dynamics prediction against HoloOcean:

```powershell
cd F:\smartcaptain\HoloOcean-2.0.1
python test2.py
```

`test2.py` is more of a model validation script than a full path-tracking demo.

## Dependency Issue Fixed

When running `test3.py`, the following error occurred:

```text
ModuleNotFoundError: No module named 'gymnasium'
```

The active interpreter was:

```text
D:\Anaconda\python.exe
```

The issue was fixed by installing:

```powershell
python -m pip install gymnasium
```

After that, the following imports were verified:

```text
gymnasium
stable_baselines3
casadi
scipy
matplotlib
skimage
```

The script then progressed past the original import error. A short trial run timed out after about 45 seconds, likely because it entered HoloOcean / MPC simulation rather than failing immediately.

## Runtime Length

`test3.py` runs until `done == True`.

`done` comes from the parent `BaseEnvironment.is_done()` and depends on:

- Reaching `goal_location`.
- Moving too far from the goal.
- Exceeding max steps.
- Collision.

The max step setting is in:

```text
HoloOcean-2.0.1/env/env_config.py
```

Inside `BASE_CONFIG`:

```python
"max_timesteps": 36000
```

With:

```python
MPC_CONFIG["dot_t"] = 0.005
```

this corresponds to:

```text
36000 * 0.005 = 180 seconds of simulation time
```

Actual wall-clock time can be much longer because each step solves an MPC optimization problem.

For quick testing, add a manual step cap in `test3.py` or reduce `max_timesteps`.

Example idea:

```python
max_steps = 500

while not done and step_idx < max_steps:
    ...
```

## How to Stop a Running MPC Script

If running in PowerShell or VS Code terminal:

```text
Ctrl + C
```

If that does not stop it:

```powershell
Get-Process python
Stop-Process -Id <PID>
```

Avoid this unless needed:

```powershell
Stop-Process -Name python
```

because it stops all Python processes.

## Recommended Integration Strategy

MPC should be integrated as a new skill, most likely:

```text
src/smart_captain/skills/path_tracking/
```

Recommended long-term structure:

```text
src/smart_captain/
  controllers/
    mpc/
      controller.py
      predictor.py

  skills/
    path_tracking/
      __init__.py
      config.py
      env.py
      policy.py
      evaluator.py
```

Suggested meaning:

```text
controllers/mpc/controller.py
```

Holds the reusable `AUV_MPC` optimizer.

```text
controllers/mpc/predictor.py
```

Holds the optional `HoveringAUVModel` dynamics predictor.

```text
skills/path_tracking/config.py
```

Holds `MPC_CONFIG` and `PATH_TRACKING_SPEC`.

```text
skills/path_tracking/env.py
```

Migrated and cleaned version of `Path_Tracing`.

```text
skills/path_tracking/policy.py
```

Wraps `AUV_MPC` with a policy-like API:

```python
class MPCPathTrackingPolicy:
    def predict(self, observation, state=None, deterministic=True):
        action = self.controller.predict(observation)
        return action, state
```

```text
skills/path_tracking/evaluator.py
```

Reports progress to the orchestration layer.

## Important Design Decision

MPC should not be treated as a Stable Baselines3 model in `ModelStore`.

Current RL skills use:

```text
skill -> SB3 model checkpoint -> model.predict(obs)
```

MPC should use:

```text
skill -> MPC controller instance -> controller.predict(obs)
```

So it is best understood as a controller-backed skill, not an RL-backed skill.

The runtime eventually needs to support mixed controllers:

```text
navigation: RL policy
obstacle_avoidance: RL policy
path_tracking: MPC controller
```

## Suggested Future Work

1. Add `casadi` to the Smart Captain requirements.
2. Create `controllers/mpc/` and move the MPC optimizer there.
3. Create `skills/path_tracking/` and migrate `task3.py` into a clean skill environment.
4. Register `path_tracking` in `skills/registry.py`.
5. Add `path_tracking` keywords to `llm/decomposer.py`.
6. Add a path-tracking evaluator to `orchestration/evaluator_registry.py`.
7. Update runtime control selection so SB3 models and MPC controllers can both be activated.
8. Test `PathTrackingEnv + MPCPathTrackingPolicy` standalone before wiring into full mission execution.

## Known Caveats

- `test3.py` imports `stable_baselines3`, `gymnasium`, and `Agents`, but the full MPC demo does not really use SB3 agents. Some imports are leftovers.
- `task3.py` defaults to circular path tracking, which is good for testing but not necessarily equivalent to "go to target".
- `task3.py` has a `get_done()` method that references `self.auv_velocity`, while the rest of the code commonly uses `self.auv_relative_velocity`. This may be a latent bug if `get_done()` is called.
- The parent environment's done logic is goal-distance based, while the default circular path is centered on the goal. This can make path completion semantics unclear.
- Running MPC can be slow because each simulation step solves a nonlinear optimization problem.

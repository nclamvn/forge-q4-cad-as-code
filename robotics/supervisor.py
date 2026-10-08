"""Deterministic supervisory reference. No motor transport or safety certification.

The production hardware watchdog and physical E-stop must work independently
of this process. Time is supplied by the caller's monotonic clock.
"""
import math


class Supervisor:
    def __init__(self, timeout_s=.25):
        if isinstance(timeout_s, bool) or not math.isfinite(timeout_s) or not .02 <= timeout_s <= 2:
            raise ValueError('Invalid watchdog timeout')
        self.timeout_s = timeout_s
        self.state = 'DISARMED'
        self.reason = 'Explicit preflight and arm required'
        self.last_t = -1.
        self.last_heartbeat = None
        self.healthy = False
        self.events = []

    def update(self, t, *, heartbeat=False, estop=False, tilt_deg=0., motor_c=25., soc=1., driver_fault=False):
        values = [t, tilt_deg, motor_c, soc]
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values) or any(type(x) is not bool for x in [heartbeat,estop,driver_fault]):
            self.state, self.reason, self.healthy = ('ESTOP' if estop is True or self.state=='ESTOP' else 'FAULT'), 'Invalid telemetry', False
            return self.snapshot()
        if t < 0 or t < self.last_t or not -180 <= tilt_deg <= 180 or not -30 <= motor_c <= 150 or not 0 <= soc <= 1:
            self.state, self.reason, self.healthy = ('ESTOP' if estop is True or self.state=='ESTOP' else 'FAULT'), 'Clock regression or telemetry range error', False
            return self.snapshot()
        self.last_t = t
        if heartbeat:
            self.last_heartbeat = t
        self.healthy = (self.last_heartbeat is not None and t-self.last_heartbeat <= self.timeout_s
                        and not estop and not driver_fault and abs(tilt_deg) <= 25 and motor_c < 70 and .25 <= soc <= 1)
        if estop:
            self.state, self.reason = 'ESTOP', 'Physical E-stop input declared'
        elif self.state != 'ESTOP' and (driver_fault or motor_c >= 70 or abs(tilt_deg) > 25 or not 0 <= soc <= 1):
            self.state, self.reason = 'FAULT', 'Driver, thermal, tilt or telemetry fault'
        elif self.state in ('ARMED', 'RUNNING') and not self.healthy:
            self.state, self.reason = 'HOLD', 'Heartbeat stale or battery reserve reached'
        return self.snapshot()

    def command(self, action):
        if action == 'reset':
            if not self.healthy:
                raise ValueError('Healthy telemetry is required to reset')
            self.state, self.reason = 'DISARMED', 'Reset completed; arm required'
        elif action == 'arm':
            if self.state != 'DISARMED' or not self.healthy:
                raise ValueError('Preflight failed or reset required')
            self.state, self.reason = 'ARMED', 'Preflight accepted'
        elif action == 'start':
            if self.state != 'ARMED' or not self.healthy:
                raise ValueError('Explicit arm with healthy telemetry required')
            self.state, self.reason = 'RUNNING', 'Mission started'
        elif action == 'hold':
            if self.state not in ('ARMED', 'RUNNING'):
                raise ValueError('Hold requires active state')
            self.state, self.reason = 'HOLD', 'Operator hold; reset required'
        else:
            raise ValueError('Unknown supervisory command')
        self.events.append(self.snapshot())
        return self.snapshot()

    def snapshot(self):
        return dict(state=self.state, reason=self.reason, command_permitted=self.state == 'RUNNING' and self.healthy,
                    reference_only=True, physical_estop_verified=False)

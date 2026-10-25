"""Engine-independent arcade handling and keyboard-to-network input mapping."""
import math


def angle_delta(target, current):
    return (target-current+180)%360-180


def read_controls(keys):
    return dict(throttle=bool(keys.get('w',0) or keys.get('up arrow',0)),
                brake=bool(keys.get('s',0) or keys.get('down arrow',0)),
                steer=int(bool(keys.get('d',0) or keys.get('right arrow',0)))-int(bool(keys.get('a',0) or keys.get('left arrow',0))),
                drift=bool(keys.get('space',0)),boost=bool(keys.get('left shift',0) or keys.get('f',0)),
                reset=bool(keys.get('r',0)))


NEUTRAL=dict(throttle=False,brake=False,steer=0,drift=False,boost=False,reset=False)


def step_handling(car, controls, dt, on_road=True):
    """Body heading and travel heading are independent during a slide.

    Low rear grip lets the body turn ahead of its momentum. Opposite steering
    reduces this angle naturally; releasing the handbrake progressively grips up.
    """
    if dt<=0: return
    dt=min(dt,.1)
    if not hasattr(car,'travel_yaw'): car.travel_yaw=car.rotation_y
    car.nitro=max(0,min(100,car.nitro))
    car.is_boosting=bool(controls['boost'] and car.nitro>0 and controls['throttle'] and car.speed>=0)
    car.nitro=max(0,min(100,car.nitro+(-28 if car.is_boosting else 6)*dt))
    top=(car.max_boost_speed if car.is_boosting else car.max_speed)*(1 if on_road else .60)
    if controls['brake']:
        if car.speed>0:
            car.speed=max(0,car.speed-car.braking*dt)
        else: car.speed=max(car.reverse_speed,car.speed-car.acceleration*.65*dt)
    elif controls['throttle']:
        car.speed=min(top,car.speed+car.acceleration*(1.6 if car.is_boosting else 1)*dt) if car.speed<=top else max(top,car.speed-car.friction*dt)
    else:
        car.speed=math.copysign(max(0,abs(car.speed)-car.friction*dt),car.speed)
    if not on_road: car.speed*=math.exp(-.65*dt)
    car.steer_angle+=(float(controls['steer'])*car.max_steer_angle-car.steer_angle)*(1-math.exp(-12*dt))
    steer=car.steer_angle/car.max_steer_angle
    handbrake=bool(controls['drift'] and car.speed>10)
    was_drifting=car.is_drifting
    if handbrake and abs(steer)>.12:
        car.is_drifting=True
    speed_factor=min(1,abs(car.speed)/12)
    high_speed=1/(1+max(0,abs(car.speed)-30)*.012)
    yaw_rate=car.turn_rate*steer*speed_factor*high_speed
    if car.speed<0: yaw_rate=-yaw_rate
    if handbrake:
        yaw_rate*=1.22
        car.speed=max(0,car.speed-.8*dt)
    car.rotation_y=(car.rotation_y+yaw_rate*dt)%360
    grip=1.65 if handbrake else (5.0 if car.is_drifting else 10.0)
    car.travel_yaw=(car.travel_yaw+angle_delta(car.rotation_y,car.travel_yaw)*(1-math.exp(-grip*dt)))%360
    slip=angle_delta(car.travel_yaw,car.rotation_y)
    # Limit the slide so a sustained handbrake turn remains recoverable.
    slip=max(-38,min(38,slip))
    car.travel_yaw=(car.rotation_y+slip)%360
    car.drift_angle=slip
    if car.speed<8 or (not handbrake and abs(slip)<4): car.is_drifting=False
    if car.is_drifting and abs(slip)>8 and car.speed>10:
        car._drift_points=getattr(car,'_drift_points',0)+abs(slip)*car.speed*.16*dt
        car.current_drift_score=int(car._drift_points)
        car.nitro=min(100,car.nitro+min(8,abs(slip)*.25)*dt)
    if was_drifting and not car.is_drifting:
        car.drift_score+=car.current_drift_score
        car.current_drift_score=0
        car._drift_points=0

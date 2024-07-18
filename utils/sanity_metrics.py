import math
from scipy.stats import norm


def num_of_failed(time, avg_failure_time, num_init):
    failed_num = num_init
    i = 1
    total_failed = 0
    while failed_num >= 1:
        distribution_range = avg_failure_time * (2 ** i)
        if distribution_range <= time:
            failed_num = num_init
        else:
            percentage = time / distribution_range
            failed_num = (0.5 + norm.ppf(percentage)+3)/12 * num_init

        total_failed += failed_num
        i += 1

    return round(total_failed)


def num_mid_flight(num_init, recover_time, failure_time):
    return (recover_time / failure_time) * num_init


def num_illuminating(num_init, num_midflight):
    return num_init - num_midflight


def time_to_arrive(max_speed, max_acceleration, max_deceleration, total_distance):
    # Time to accelerate to max speed
    time_accelerate = max_speed / max_acceleration
    time_decelerate = max_speed / max_deceleration

    # Distance covered during acceleration (and deceleration, since it's symmetric)
    distance_accelerate = 0.5 * max_acceleration * time_accelerate ** 2
    distance_decelerate = 0.5 * max_deceleration * time_decelerate ** 2

    # Distance covered at max speed
    distance_max_speed = total_distance - (distance_accelerate + distance_decelerate)

    # If the total distance is less than the sum of acceleration and deceleration distances
    if distance_max_speed < 0:
        # Calculate the distance at which we need to start decelerating
        critical_distance = total_distance / 2
        time_accelerate = math.sqrt(2 * critical_distance / max_acceleration)
        time_decelerate = time_accelerate  # symmetric
        return time_accelerate + time_decelerate

    # Time to travel the remaining distance at max speed
    time_max_speed = distance_max_speed / max_speed

    # Total time
    total_time = time_accelerate + time_max_speed + time_accelerate  # last term is for deceleration

    return total_time

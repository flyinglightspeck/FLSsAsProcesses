import numpy as np


def hausdorff_distance(a, b):
    # dist = np.zeros(a.shape[0])
    # t = b - a
    # for i in range(a.shape[0]):
    #     dist[i] = max(compute_distance(a + t[i], b), compute_distance(b, a + t[i]))
    #
    # return np.min(dist)

    ca = np.average(a, axis=0)
    cb = np.average(b, axis=0)
    t2 = cb - ca

    dist2 = max(compute_distance(a + t2, b), compute_distance(b, a + t2))
    return dist2


def compute_distance(a, b):
    dist = np.zeros(a.shape[0])
    for i in range(a.shape[0]):
        dist[i] = np.min(np.linalg.norm(b - a[i], axis=1))
    return np.max(dist)

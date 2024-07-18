import time

import numpy as np
from scipy.spatial import distance


def knn(points, k=1):
    d = distance.squareform(distance.pdist(points))
    closest = np.argsort(d, axis=1)
    return closest, np.take_along_axis(d, closest, 1)


if __name__ == "__main__":
    t = time.time()
    pts = np.random.rand(6000, 3)
    # print(np.round(pts, 1))

    idx, dist = knn(pts, 4)
    print(time.time() - t)
    # print(np.round(idx, 1))
    # print(np.round(dist, 1))


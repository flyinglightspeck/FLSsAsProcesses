import math

import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.animation as animation
from multiprocessing import shared_memory
import numpy as np
import scipy


# mpl.use('macosx')


def plot_point_cloud(ptcld, name):
    tnrfont = {'fontname': 'Times News Roman'}
    ticks_gap = 10
    length = math.ceil(np.max(ptcld[:, 0]) / ticks_gap) * ticks_gap
    width = math.ceil(np.max(ptcld[:, 1]) / ticks_gap) * ticks_gap
    height = math.ceil(np.max(ptcld[:, 2]) / ticks_gap) * ticks_gap
    print(length, width, height)
    exit()
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(projection='3d')
    ax.scatter(ptcld[:, 0], ptcld[:, 1], ptcld[:, 2], c='blue', s=.45, alpha=1)
    ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 1.0))
    ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 1.0))
    ax.zaxis.set_pane_color((0, 0, 0, 0.025))
    ax.view_init(elev=14, azim=136, roll=0)
    ax.axes.set_xlim3d(left=0, right=length)
    ax.axes.set_ylim3d(bottom=0, top=width)
    ax.axes.set_zlim3d(bottom=0, top=height)
    ax.set_aspect('equal')
    ax.grid(False)
    ax.set_xticks(range(0, length + 1, length))
    ax.set_yticks(range(0, width + 1, width))
    ax.set_zticks(range(0, height + 1, height))
    ax.tick_params(labelsize=16)
    # plt.savefig(f'../results/{name}.png')
    plt.show()


def update(num, graph, shm_name, count):
    shared_mem = shared_memory.SharedMemory(name=shm_name)
    shared_array = np.ndarray((count, 3), dtype=np.float64, buffer=shared_mem.buf)
    # print(graph._offsets3d)
    graph._offsets3d = (shared_array[:, 0], shared_array[:, 1], shared_array[:, 2])
    return graph,


if __name__ == '__main__':
# for name in ['chess', 'dragon', 'skateboard', 'racecar']:
    name = 'racecar'
    mat = scipy.io.loadmat(f'../assets/{name}.mat')
    point_cloud = mat['p']
    plot_point_cloud(point_cloud, name)

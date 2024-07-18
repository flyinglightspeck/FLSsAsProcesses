import random

import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as st
import matplotlib as mpl



def left_half_exponential(n):
    alpha, beta = 10, 0.8
    return random.betavariate(alpha, beta) * n


def beta_pdf():
    fig = plt.figure(figsize=(5, 4), layout='constrained')
    ax = fig.add_subplot()
    a, b = 5, 1
    mean, var, skew, kurt = st.beta.stats(a, b, moments='mvsk')

    x = np.linspace(0, 1, 100)
    ax.plot(x, st.beta.pdf(x, 10, 0.8), lw=3, label=r'$\alpha=10, \beta=0.8$')
    ax.plot(x, st.beta.pdf(x, 5, 1), label=r'$\alpha=5, \beta=1$')
    ax.plot(x, st.beta.pdf(x, 2, 2), label=r'$\alpha=2, \beta=2$')
    ax.plot(x, st.beta.pdf(x, 1, 3), label=r'$\alpha=1, \beta=3$')

    ax.set_title('PDF', loc='left')
    # ax.set_xlabel('Time (Second)', loc='right')
    ax.spines['top'].set_color('white')
    ax.spines['right'].set_color('white')
    ax.margins(0, 0)
    ax.legend()
    ax.set_ylim(0, 2.5)
    plt.savefig('betaDist.png', dpi=300)


if __name__ == '__main__':
    mpl.rcParams['font.family'] = 'Times New Roman'

    beta_pdf()
    exit()
    data = []
    alpha, beta = 10, 0.8
    for i in range(1000000):
        r = random.betavariate(alpha, beta)
        # while x > 60:
        #     x = np.random.exponential(scale=1 / lambda_param)

        data.append(r * 60)
    count, bins, ignored = plt.hist(data, bins=100, density=False)
    print(np.mean(data))
    plt.show()
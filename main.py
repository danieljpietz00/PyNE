import numpy as np
from NE import *


class MySystem(NESystem):
    def __init__(self, x, xdot):
        super(MySystem, self).__init__()

        self.input_map = np.eye(3)
        self.coeff1 = 1
        self.coeff2 = 2

        self.link0 = Link(
            parent=self,
            position=[0, x[0], 0],
            rotation=np.eye(3),
            mass=1,
            COM=[0, 1, 0],
            inertia=np.eye(3),
            PMap=sparse((3, 3), (0, 0))
        )

        self.link1 = Link (
            parent=self,
            position = [0, 0, 0],
            rotation = rotx(x[1]),
            mass=1,
            COM=[0, 1, 0],
            inertia=np.eye(3),
            RMap=sparse((3, 3), (0, 1))
        )

        self.link2 = Link(
            parent=self.link1,
            position=[0, 1, 0],
            rotation=rotx(x[2]),
            mass=1,
            COM=[0, 1, 0],
            inertia=np.eye(3),
            RMap=sparse((3, 3), (0, 2))
        )

        self.link1.add_force(Gravity([0, 0, -9.81]))
        self.link2.add_force(Gravity([0, 0, -9.81]))

        self.link0.add_force(ViscousFriction(1))
        self.link1.add_force(ViscousFriction(1))
        self.link2.add_force(ViscousFriction(1))

    def barrier(self, x, xdot):
        return np.sum(x)

    def d_barrier(self, x, xdot, xddot):
        return np.sum(xdot)

    def G_barrier(self, x, xdot):
        return np.array([[1, 1, 1, 0, 0, 0]]).transpose()

    def H_barrier(self, x, xdot):
        return np.zeros((6, 6))


results = RungeKutta(MySystem()).dsolve([0,0,0], [0, 0 ,0], (0, 20)).df()

results.plot(x='time', y=['x0', 'x1', 'x2'])
plt.show()

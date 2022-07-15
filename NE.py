import numpy as np
import pandas as pd
from functions import *


class _Link(object):
    def __init__(self, mass, COM, inertia):
        self.mass = mass
        self.COM = COM
        self.inertia = inertia
        self.first_mass_moment_skew = skew(mass * self.COM)
        self.mass_ident = np.diag(3 * [mass])
        self.children = []
        self.forces = []

    def add_child(self, child):
        self.children.append(child)

    def add_force(self, force):
        force.link = self
        self.forces.append(force)

    def update(self):
        self.kinematics()
        self.dynamics()
        for child in self.children:
            child.update()
            self.H += child.H.astype(float)
            self.d += child.d.astype(float)
            self.F += child.F.astype(float)

    def dynamics(self):
        m_corner_elem = self.first_mass_moment_skew @ self.rotation_global.transpose()

        self.M = np.block(
            [
                [self.inertia, m_corner_elem],
                [m_corner_elem.transpose(), self.mass_ident],
            ]
        )

        jtm = self.Jacobian.transpose() @ self.M

        self.H = jtm @ self.Jacobian

        omega_global_squared = self.omega_global_skewed @ self.omega_global_skewed

        dPrime = np.block(
            [
                [self.omega_global_skewed @ self.inertia @ self.omega_global],
                [self.mass * self.rotation_global @ omega_global_squared @ self.COM],
            ]
        )

        dot_jacob_dot_x_product = self.JacobianDot @ self.xdot
        self.d = jtm @ dot_jacob_dot_x_product + self.Jacobian.transpose() @ dPrime

        F = np.zeros((6, 1))
        fJoint = np.zeros((len(self.d), 1))

        for f in self.forces:
            if isinstance(f, JointForce):
                fJoint += f.get()
            else:
                pos, vec = f.get()
                F += np.block([[skew(pos) @ self.rotation_global.transpose() @ vec],
                               [self.mass * vec]]).astype(float)

        self.F = self.Jacobian.transpose() @ F + fJoint


class Root(_Link):
    def __init__(self, mass, COM, inertia):
        super(Root, self).__init__(mass, COM, inertia)

    def __init_subclass__(cls, **kwargs):
        cls.___init___ = cls.__init__

        def __init_wrapper__(self):
            pass

        cls.__init__ = __init_wrapper__

    def kinematics(self):
        self.x = np.reshape(self.x, (len(self.x), 1))
        self.xdot = np.reshape(self.xdot, (len(self.xdot), 1))
        temp = self.Jacobian @ self.xdot
        self.omega_global = temp[0:3]
        self.omega_global_skewed = skew(self.omega_global)
        self.velocity = temp[4:6]

    def eval(self, x, xdot):
        self.x = np.reshape(x, (len(x), 1)).astype(float)
        self.xdot = np.reshape(xdot, (len(x), 1)).astype(float)
        self.___init___(x, xdot)
        self.update()
        return np.linalg.solve(self.H, self.F - self.d)

    def __call__(self, x, xdot):
        return self.eval(x, xdot)


class Link(_Link):
    def __init__(self, parent, mass, COM, inertia, position, rotation, IHat, ITilde):
        super(Link, self).__init__(mass, COM, inertia)
        self.IHat = IHat
        self.ITilde = ITilde
        self.position = position
        self.rotation = rotation
        self.parent = parent
        self.parent.add_child(self)
        self.x = np.reshape(parent.x, (len(parent.x), 1))
        self.xdot = np.reshape(parent.xdot, (len(parent.xdot), 1))
        self.dof = len(self.x)

    def kinematics(self):
        #
        # We are going to use a lot of skewed vectors and transposed matrices. We can save a little bit of time by
        # precomputing these values
        #

        self.rotation_global = (self.parent.rotation_global @ self.rotation)

        self.omega_local = self.IHat @ self.xdot
        self.omega_global = self.parent.omega_global + self.rotation @ self.omega_local
        self.velocity = self.ITilde @ self.xdot

        self.rotation_local_transpose = self.rotation.transpose()
        self.position_local_skewed = skew(self.position)
        self.velocity_local_skewed = skew(self.velocity)

        self.omega_local_skewed = skew(self.omega_local)
        self.omega_global_skewed = skew(self.omega_global)

        self.JacobianPrime = np.block(
            [
                [self.rotation_local_transpose, np.zeros((3, 3))],
                [
                    self.parent.rotation_global @ self.position_local_skewed.transpose(),
                    np.eye(3),
                ],
            ]
        )

        self.Jacobian = self.JacobianPrime @ self.parent.Jacobian + np.block(
            [[self.IHat], [self.parent.rotation_global @ self.ITilde]]
        )

        self.JacobianStar = np.block(
            [
                [
                    self.omega_local_skewed @ self.parent.rotation_global,
                    np.zeros((3, 3)),
                ],
                [
                    -self.parent.rotation_global
                    @ (
                            self.parent.omega_global_skewed @ self.position_local_skewed
                            + self.velocity_local_skewed
                    ),
                    np.zeros((3, 3)),
                ],
            ]
        )

        self.JacobianDot = (
                self.JacobianStar @ self.parent.Jacobian
                + self.JacobianPrime @ self.parent.JacobianDot
                + np.block(
            [
                [np.zeros((3, self.dof))],
                [
                    self.parent.rotation_global
                    @ self.omega_local_skewed
                    @ self.ITilde
                ],
            ]
        )
        )


class Force(object):
    def __init__(self):
        pass


class JointForce(Force):
    def __init__(self):
        pass


class Gravity(Force):
    def __init__(self, vector):
        self.link = None
        self.vector = vector

    def get(self):
        return self.link.COM, self.vector * self.link.mass


class Friction(JointForce):
    pass


class ViscousFriction(Friction):

    def __init__(self, coefficient):
        self.link = None
        self.coefficient = coefficient

    def get(self):
        return -self.coefficient * (self.link.IHat + self.link.ITilde) @ self.link.xdot


class Solver(object):

    class Solution(object):
        def __init__(self, x, xdot):
            self.x = x
            self.xdot = xdot

        def df(self):
            pass

    def __init__(self, system):
        self.system = system
        self.tX = []
        self.tXDot = []

    def solve(self, x0, dx0, tRange, tStep):
        timestamp = np.arange(*tRange, tStep)
        self.tX = np.zeros((len(timestamp), len(x0)))
        self.tXDot = self.tX
        self.tX[0] = x0
        self.tXDot[0] = dx0
        for i, t in enumerate(timestamp[1:]):
            (self.tX[i + 1], self.tXDot[i + 1]) = (x.flatten().astype(float) for x in self.step(tStep, self.tX[i], self.tXDot[i]))

        return self.Solution(self.tX, self.tXDot)

    def step(self):
        raise

    pass




class RungeKutta(Solver):

    def __init__(self, system):
        super(RungeKutta, self).__init__(system)

    def step(self, h, x=None, xdot=None):
        if x is None and xdot is None:
            (x, xdot) = (self.system.x, self.system.xdot)
        x = np.reshape(x, (len(x), 1)).astype(float)
        xdot = np.reshape(xdot, (len(x), 1)).astype(float)
        k1 = self.system.eval(x, xdot)
        k2 = self.system.eval(x + h*(xdot / 2), xdot + h*(k1/2))
        k3 = self.system.eval(x + h * (xdot / 2), xdot + h * (k2 / 2))
        k4 = self.system.eval(x + h*xdot, xdot + h*k3)
        dxdot = (h / 6) * (k1 + 2*(k2 + k3) + k4)

        return (x + xdot, xdot + dxdot)

    pass
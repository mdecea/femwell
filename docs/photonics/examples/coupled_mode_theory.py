# ---
# jupyter:
#   jupytext:
#     custom_cell_magics: kql
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: env_3.11
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Coupled mode theory

# %% [markdown]
# ```{caution}
# **This example is under construction, results are not yet all correct**
# ```

# %% [markdown]
# https://www.fiberoptics4sale.com/blogs/wave-optics/coupled-mode-theory
# https://www.fiberoptics4sale.com/blogs/wave-optics/two-mode-coupling

# %% tags=["hide-input"]
from collections import OrderedDict

import matplotlib.pyplot as plt
import numpy as np
from scipy.constants import epsilon_0, speed_of_light
from scipy.integrate import solve_ivp
from shapely.geometry import Polygon
from skfem import Basis, ElementTriP0, Mesh
from skfem.io import from_meshio

from femwell.mesh import mesh_from_OrderedDict
from femwell.mode_solver import (
    calculate_coupling_coefficient,
    calculate_hfield,
    calculate_overlap,
    compute_modes,
    plot_mode,
)

# %% [markdown]
# Let's set up the geometry!
# It's the cross-section of two parallel waveguides with different widths:

# %% tags=["remove-stderr", "hide-input"]
w_sim = 4
h_clad = 1
h_box = 1
w_core_1 = 0.45
w_core_2 = 0.46
gap = 0.4
h_core = 0.22
offset_heater = 2.2
h_heater = 0.14
w_heater = 2

wavelength = 1.55
k0 = 2 * np.pi / wavelength

polygons = OrderedDict(
    core_1=Polygon(
        [
            (-w_core_1 - gap / 2, 0),
            (-w_core_1 - gap / 2, h_core),
            (-gap / 2, h_core),
            (-gap / 2, 0),
        ]
    ),
    core_2=Polygon(
        [
            (w_core_2 + gap / 2, 0),
            (w_core_2 + gap / 2, h_core),
            (gap / 2, h_core),
            (gap / 2, 0),
        ]
    ),
    clad=Polygon(
        [
            (-w_sim / 2, 0),
            (-w_sim / 2, h_clad),
            (w_sim / 2, h_clad),
            (w_sim / 2, 0),
        ]
    ),
    box=Polygon(
        [
            (-w_sim / 2, 0),
            (-w_sim / 2, -h_box),
            (w_sim / 2, -h_box),
            (w_sim / 2, 0),
        ]
    ),
)

resolutions = dict(
    core_1={"resolution": 0.03, "distance": 1},
    core_2={"resolution": 0.03, "distance": 1},
)

mesh = from_meshio(
    mesh_from_OrderedDict(polygons, resolutions, filename="mesh.msh", default_resolution_max=0.2)
)
mesh.draw().show()

# %% [markdown]
# First we plot the symmetric and the asymmetric modes of the geometry with both waveguides:

# %%
basis0 = Basis(mesh, ElementTriP0(), intorder=4)

epsilon = basis0.zeros() + 1.444**2
epsilon[basis0.get_dofs(elements=("core_1", "core_2"))] = 3.4777**2
# basis0.plot(epsilon, colorbar=True).show()
lams_both, basis, xs_both = compute_modes(
    basis0, epsilon, wavelength=wavelength, mu_r=1, num_modes=2
)
plot_mode(basis, np.real(xs_both[0]), direction="x")
plt.show()
plot_mode(basis, np.real(xs_both[1]), direction="x")
plt.show()
print("Refractive index of symmetric and assymetric mode:", lams_both)
# https://www.fiberoptics4sale.com/blogs/wave-optics/directional-couplers
print(
    f"Maximum power transfer after {np.pi / (2 * np.pi / wavelength * np.real(lams_both[0] - lams_both[1]))} um prop length"
)

# %% [markdown]
# And then we plot the modes of each waveguide while setting the shape of the other one to oxide

# %%
epsilon = basis0.zeros() + 1.444**2
epsilon[basis0.get_dofs(elements="core_1")] = 3.4777**2
# basis0.plot(epsilon, colorbar=True).show()
lams_1, basis, xs_1 = compute_modes(basis0, epsilon, wavelength=wavelength, mu_r=1, num_modes=1)
print("Effective refractive index of the mode of the first waveguide", lams_1)
plot_mode(basis, np.real(xs_1[0]), direction="x")
plt.show()

epsilon_2 = basis0.zeros() + 1.444**2
epsilon_2[basis0.get_dofs(elements="core_2")] = 3.4777**2
# basis0.plot(epsilon_2, colorbar=True).show()
lams_2, basis, xs_2 = compute_modes(basis0, epsilon_2, wavelength=wavelength, mu_r=1, num_modes=1)
print("Effective refractive index of the mode of the second waveguide", lams_2)
plot_mode(basis, np.real(xs_2[0]), direction="x")
plt.show()

# %%
length = 200
ts = np.linspace(0, length, 1000)

# %%
epsilons = [epsilon, epsilon_2]
modes = [(lam, x, 0) for lam, x in zip(lams_1, xs_1)] + [
    (lam, x, 1) for lam, x in zip(lams_2, xs_2)
]

overlap_integrals = np.zeros((len(modes), len(modes)), dtype=complex)
for i, (lam_i, E_i, epsilon_i) in enumerate(modes):
    for j, (lam_j, E_j, epsilon_j) in enumerate(modes):
        H_i = calculate_hfield(
            basis,
            E_i,
            lam_i * (2 * np.pi / 1.55),
            omega=2 * np.pi / wavelength * speed_of_light,
        )
        H_j = calculate_hfield(
            basis,
            E_j,
            lam_j * (2 * np.pi / 1.55),
            omega=2 * np.pi / wavelength * speed_of_light,
        )
        overlap_integrals[i, j] = calculate_overlap(basis, E_i, H_i, basis, E_j, H_j)

print("overlap", overlap_integrals)
# plt.imshow(np.abs(overlap_integrals))
# plt.colorbar()
# plt.show()

coupling_coefficients = np.zeros((len(modes), len(modes)), dtype=complex)
for i, (lam_i, E_i, epsilon_i) in enumerate(modes):
    for j, (lam_j, E_j, epsilon_j) in enumerate(modes):
        coupling_coefficients[i, j] = (
            k0
            * speed_of_light
            * epsilon_0
            * calculate_coupling_coefficient(
                basis0, epsilons[(epsilon_j + 1) % 2] - 1.444**2, basis, E_i, E_j
            )
            * 0.5
        )


print(coupling_coefficients)
# plt.imshow(np.abs(coupling_coefficients))
# plt.colorbar()
# plt.show()

kappas = np.array(
    [
        [
            (
                coupling_coefficients[i, j]
                - overlap_integrals[i, (i + 1) % 2]
                * coupling_coefficients[(i + 1) % 2, j]
                / overlap_integrals[(i + 1) % 2, (i + 1) % 2]
            )
            / (
                1
                - overlap_integrals[0, 1]
                * overlap_integrals[1, 0]
                / (overlap_integrals[0, 0] * overlap_integrals[1, 1])
            )
            for i in range(2)
        ]
        for j in range(2)
    ]
)
print(kappas)

delta = 0.5 * (np.real(lams_1[0]) * k0 + kappas[1, 1] - (np.real(lams_2[0]) * k0 + kappas[0, 0]))
print(delta, np.real(lams_1[0]) * k0, kappas[1, 1])

beta_c = (kappas[0, 1] * kappas[1, 0] + delta**2) ** 0.5

print(np.pi / (2 * beta_c))

eta = np.abs(kappas[1, 0] ** 2 / beta_c**2) * np.sin(beta_c * 1e3)
print("eta", eta, np.abs(kappas[1, 0] ** 2 / beta_c**2))

plt.plot(ts, 1 - np.abs(kappas[1, 0] ** 2 / beta_c**2 * np.sin(beta_c * ts) ** 2))
plt.plot(ts, np.abs(kappas[1, 0] ** 2 / beta_c**2 * np.sin(beta_c * ts) ** 2))
plt.show()

# %% [markdown]
# see http://home.iitj.ac.in/~k.r.hiremath/research/thesis.pdf , not yet finished


# %%
def fun(t, y):
    phase_matrix = [
        [np.exp(2j * np.pi / wavelength * (lam_i - lam_j) * t) for lam_j, E_j, epsilon_j in modes]
        for lam_i, E_i, epsilon_i in modes
    ]
    matrix = (
        np.linalg.inv(overlap_integrals * phase_matrix)
        @ (coupling_coefficients * phase_matrix)
        * -1j
    )
    return (matrix @ y).ravel()


result = solve_ivp(fun, [0, length], np.array((1, 0), dtype=complex), t_eval=ts)
ys = result.y.T

plt.plot(ts, np.abs(np.array(ys)[:, 0]) ** 2, "r")
plt.plot(ts, 1 - np.abs(np.array(ys)[:, 0]) ** 2, "r")
# plt.plot(ts, np.array(ys).imag.reshape((-1,)+matrix.shape)@(1,0), 'g')
plt.show()

# %% [markdown]
# ## two modes

# %%
R = []

lam_i = lams_1[0]
E_i = xs_1[0]

for lam_j, E_j in zip(lams_both, xs_both):
    H_i = calculate_hfield(
        basis,
        E_i,
        lam_i * (2 * np.pi / 1.55),
        omega=2 * np.pi / wavelength * speed_of_light,
    )
    H_j = calculate_hfield(
        basis,
        E_j,
        lam_j * (2 * np.pi / 1.55),
        omega=2 * np.pi / wavelength * speed_of_light,
    )
    R.append(calculate_overlap(basis, E_i, H_i, basis, E_j, H_j) ** 2)

P = (
    R[0] ** 2
    + R[1] ** 2
    + 2 * R[0] * R[1] * np.cos(2 * np.pi / wavelength * (lams_both[0] - lams_both[1]) * ts)
)

plt.plot(ts, P)
plt.show()
# %%
plt.plot(ts, P)


plt.plot(ts, 1 - np.abs(kappas[1, 0] ** 2 / beta_c**2) * np.sin(beta_c * ts) ** 2)

plt.plot(ts, np.abs(np.array(ys)[:, 0]) ** 2, "r")
plt.plot(ts, 1 - np.abs(np.array(ys)[:, 0]) ** 2, "r")
# plt.plot(ts, np.array(ys).imag.reshape((-1,)+matrix.shape)@(1,0), 'g')
plt.show()

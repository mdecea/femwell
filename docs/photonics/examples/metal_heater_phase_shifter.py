
from collections import OrderedDict

from tqdm.auto import tqdm
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, LineString

from skfem import Basis, ElementTriP0
from skfem.io import from_meshio
from femwell.mesh import mesh_from_OrderedDict
from femwell.mode_solver import compute_modes, plot_mode
from femwell.thermal import solve_thermal

# Simulating the TiN TOPS heater in https://doi.org/10.1364/OE.27.010456

w_sim = 8 * 2
h_clad = 2.8
h_box = 1
w_core = 0.5
h_core = 0.22
offset_heater = 2.2
h_heater = .14
w_heater = 2

polygons = OrderedDict(
    bottom=LineString([
        (-w_sim / 2, -h_core / 2 - h_box),
        (w_sim / 2, -h_core / 2 - h_box)
    ]),
    core=Polygon([
        (-w_core / 2, -h_core / 2),
        (-w_core / 2, h_core / 2),
        (w_core / 2, h_core / 2),
        (w_core / 2, -h_core / 2),
    ]),
    heater=Polygon([
        (-w_heater / 2, -h_heater / 2 + offset_heater),
        (-w_heater / 2, h_heater / 2 + offset_heater),
        (w_heater / 2, h_heater / 2 + offset_heater),
        (w_heater / 2, -h_heater / 2 + offset_heater),
    ]),
    clad=Polygon([
        (-w_sim / 2, -h_core / 2),
        (-w_sim / 2, -h_core / 2 + h_clad),
        (w_sim / 2, -h_core / 2 + h_clad),
        (w_sim / 2, -h_core / 2),
    ]),
    box=Polygon([
        (-w_sim / 2, -h_core / 2),
        (-w_sim / 2, -h_core / 2 - h_box),
        (w_sim / 2, -h_core / 2 - h_box),
        (w_sim / 2, -h_core / 2),
    ])
)

resolutions = dict(
    core={"resolution": 0.04, "distance": 1},
    clad={"resolution": 0.6, "distance": 1},
    box={"resolution": 0.6, "distance": 1},
    heater={"resolution": 0.1, "distance": 1}
)

mesh = from_meshio(mesh_from_OrderedDict(polygons, resolutions, default_resolution_max=.6))

currents = np.linspace(0.007, 10e-3, 10) / polygons['heater'].area
neffs = []

for current in tqdm(currents):
    basis0 = Basis(mesh, ElementTriP0(), intorder=4)
    thermal_conductivity_p0 = basis0.zeros()
    for domain, value in {"core": 148, "box": 1.38, "clad": 1.38, "heater": 28}.items():
        thermal_conductivity_p0[basis0.get_dofs(elements=domain)] = value
    thermal_conductivity_p0 *= 1e-12  # 1e-12 -> conversion from 1/m^2 -> 1/um^2

    basis, temperature = solve_thermal(basis0, thermal_conductivity_p0,
                                        specific_conductivity={"heater": 2.3e6},
                                        current_densities={"heater": current},
                                        fixed_boundaries={'bottom': 0})
    # basis.plot(temperature, colorbar=True)
    # plt.show()

    temperature0 = basis0.project(basis.interpolate(temperature))
    epsilon = basis0.zeros() + (1.444 + 1.00e-5 * temperature0) ** 2
    epsilon[basis0.get_dofs(elements='core')] = \
        (3.4777 + 1.86e-4 * temperature0[basis0.get_dofs(elements='core')]) ** 2
    # basis0.plot(epsilon, colorbar=True).show()

    lams, basis, xs = compute_modes(basis0, epsilon, wavelength=1.55, mu_r=1, num_modes=1)

    # plot_mode(basis, xs[0])
    # plt.show()

    neffs.append(np.real(lams[0]))

print(f'Phase shift: {2 * np.pi / 1.55 * (neffs[-1] - neffs[0]) * 320}')
plt.xlabel('Power')
plt.ylabel('$n_{eff}$')
plt.plot(currents, neffs)
plt.show()
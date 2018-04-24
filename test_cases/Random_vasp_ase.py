from structure import random_crystal
from pymatgen.core.structure import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from spglib import get_symmetry_dataset
from ase.io import read, write
from ase.calculators.vasp import Vasp
from random import randint
from vasprun import vasprun
import os

"""
This is a script to generate random crystals 
and then perform multiple steps of optimization with ASE-VASP 
todo: add timing function to estimate the time cost for each structure
"""
#Test paramaters: [sg_min, sg_max], [species], [numIons]
pstress = 50.0
maxvec = 25.0
minvec = 2.5
maxangle = 150
minangle = 30

setup = {'B': '_s'} #use soft pp to speed up calc 

def pymatgen2ase(struc):
    atoms = Atoms(symbols = struc.atomic_numbers, cell = struc.lattice.matrix)
    atoms.set_scaled_positions(struc.frac_coords)
    return atoms

def ase2pymatgen(struc):
    lattice = struc._cell
    coordinates = struc.get_scaled_positions()
    species = struc.get_chemical_symbols()
    return Structure(lattice, species, coordinates)

def symmetrize_cell(struc, mode='C'):
    """
    symmetrize structure from pymatgen, and return the struc in conventional/primitive setting
    Args:
    struc: ase type
    mode: output conventional or primitive cell
    """
    P_struc = ase2pymatgen(struc)
    finder = SpacegroupAnalyzer(P_struc,symprec=0.06,angle_tolerance=5)
    if mode == 'C':
        P_struc = finder.get_conventional_standard_structure()
    else:
        P_struc = finder.get_primitive_standard_structure()

    return pymatgen2ase(P_struc)

def set_vasp(level=0, pstress=0.0000, setup=None):
    default0 = {'xc': 'pbe',
            'npar': 8,
            'kgamma': True,
            'lcharg': False,
            'lwave': False,
            'ibrion': 2,
            'pstress': pstress,
            'setups': setup,
            }
    if level==0:
        default1 = {'prec': 'low',
                'algo': 'normal',
                'kspacing': 0.4,
                'isif': 2,
                'ediff': 1e-2,
                'nsw': 50,
                'potim': 0.02,
                }
    elif level==1:
        default1 = {'prec': 'normal',
                'algo': 'normal',
                'kspacing': 0.3,
                'isif': 3,
            'ediff': 1e-3,
                'nsw': 50,
                'potim': 0.05,
                }
    elif level==2:
        default1 = {'prec': 'accurate',
                'kspacing': 0.2,
                'isif': 3,
            'ediff': 1e-3,
                'nsw': 50,
                'potim': 0.1,
                }
    elif level==3:
        default1 = {'prec': 'accurate',
                'encut': 600,
                'kspacing': 0.15,
                'isif': 3,
            'ediff': 1e-4,
                'nsw': 50,
                }
    elif level==4:
        default1 = {'prec': 'accurate',
                'encut': 600,
                'kspacing': 0.15,
                'isif': 3,
            'ediff': 1e-4,
                'nsw': 0,
                }

    dict_vasp = dict(default0, **default1)
    return Vasp(**dict_vasp)

def read_OUTCAR(path='OUTCAR'):
    """read time and ncores info from OUTCAR"""
    time = 0
    ncore = 0
    for line in open(path, 'r'):
        if line.rfind('running on  ') > -1:
            ncore = int(line.split()[2])
        elif line.rfind('Elapsed time ') > -1:
            time = float(line.split(':')[-1])

    return time, ncore

def good_lattice(struc):
    para = struc.get_cell_lengths_and_angles()
    if (max(para[:3])<maxvec) and (max(para[3:])<maxangle) and (min(para[3:])>minangle):
        return True
    else:
        return False

def optimize(struc, dir1):
    os.mkdir(dir1)
    os.chdir(dir1)
    time0 = 0
    # Step1: ISIF = 2
    struc.set_calculator(set_vasp(level=0, pstress=pstress, setup=setup))
    print(struc.get_potential_energy())

    # Step2: ISIF = 3
    struc = read('CONTCAR',format='vasp')
    struc.set_calculator(set_vasp(level=1, pstress=pstress, setup=setup))
    print(struc.get_potential_energy())
    time, ncore = read_OUTCAR()
    time0 += time

    # Step3: ISIF = 3 with high precision 
    struc = read('CONTCAR',format='vasp')
    if good_lattice(struc):
        struc.set_calculator(set_vasp(level=2, pstress=pstress))
        print(struc.get_potential_energy())
        time, ncore = read_OUTCAR()
        time0 += time
        struc = read('CONTCAR',format='vasp')

        if good_lattice(struc):
            struc.set_calculator(set_vasp(level=3, pstress=pstress))
            time, ncore = read_OUTCAR()
            time0 += time
            print(struc.get_potential_energy())
            struc = read('CONTCAR',format='vasp')
           
            if good_lattice(struc):
                struc.set_calculator(set_vasp(level=4, pstress=pstress))
                struc.get_potential_energy()
                time, ncore = read_OUTCAR()
                time0 += time
                result = vasprun().values
                spg = get_symmetry_dataset(struc, symprec=5e-2)['international']
                print('#####%-10s %12.6f %6.2f %8.2f %4d %12s' % 
                (dir1, result['calculation']['energy_per_atom'], result['gap'], time0, ncore, spg))

species = ['B']
factor = 1.0
dir0 = os.getcwd()

for i in range(50):
    os.chdir(dir0)
    numIons = [12]
    run = True
    while run:
        #numIons[0] = randint(8,16)
        sg = randint(2,230)
        #print(sg, species, numIons, factor)
        rand_crystal = random_crystal(sg, species, numIons, factor)
        if rand_crystal.valid:
            run = False
    try:
        struc = rand_crystal.struct
        label = str(struc.formula).replace(" ","")
        dir1 = str(i)+'-'+label
        struc.to(fmt="poscar", filename = '1.vasp')
        struc = read('1.vasp',format='vasp')
        ans = get_symmetry_dataset(struc, symprec=1e-1)['number']
        print('Space group  requested: ', sg, 'generated', ans)
        optimize(struc, dir1)
    except:
        print('something is wrong')

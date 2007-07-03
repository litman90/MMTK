# This module constructs molecules and universes corresponding exactly
# to the contents of a PDB file, using residue and atom names as
# given in the file.
#
# Written by Konrad Hinsen
# last revision: 2007-7-2
#

"""
This module permits the construction of molecular objects that correspond
exactly to the contents of a PDB file. It is used for working with
experimental data. Note that most force fields cannot be applied to the
systems generated in this way.
"""

import MMTK
from MMTK.MoleculeFactory import MoleculeFactory
from Scientific.Geometry import Vector

class PDBMoleculeFactory(MoleculeFactory):

    """
    A PDBMoleculeFactory generates molecules and universes from the
    contents of a PDBConfiguration. Nothing is added or left out, and
    the atom and residue names are exactly those of the original PDB
    file.
    """

    def __init__(self, pdb_conf):
        """
        @param pdb_conf: a PDBConfiguration
        @type pdb_conf: L{MMTK.PDB.PDBConfiguration}
        """
        MoleculeFactory.__init__(self)
        self.pdb_conf = pdb_conf
        self.peptide_chains = []
        self.nucleotide_chains = []
        self.molecules = {}
        self.makeAll()

    def retrieveMolecules(self):
        """
        Constructs Molecule objects corresponding to the contents of the
        PDBConfiguration. Each peptide or nucleotide chain becomes
        one molecule. For residues that are neither amino acids nor
        nucleic acids, each residue becomes one molecule.

        @returns: a list of Molecule objects
        @rtype: C{list}
        """
        objects = []
        for chain in self.peptide_chains:
            objects.append(self.retrieveMolecule(chain))
        for chain in self.nucleotide_chains:
            objects.append(self.retrieveMolecule(chain))
        for mollist in self.molecules.values():
            for residue in mollist:
                objects.append(self.retrieveMolecule(residue))
        return objects

    def retrieveUniverse(self):
        """
        Constructs an empty universe (OrthrhombicPeriodicUniverse or
        ParallelepipedicPeriodicUniverse) representing the
        unit cell of the crystal.
        
        @returns: a universe
        @rtype: L{MMTK.Universe.Universe}
        """
        e1 = self.pdb_conf.from_fractional(Vector(1., 0., 0.))
        e2 = self.pdb_conf.from_fractional(Vector(0., 1., 0.))
        e3 = self.pdb_conf.from_fractional(Vector(0., 0., 1.))
        if abs(e1.normal()*Vector(1., 0., 0.)-1.) < 1.e-15 \
               and abs(e2.normal()*Vector(0., 1., 0.)-1.) < 1.e-15 \
               and abs(e3.normal()*Vector(0., 0., 1.)-1.) < 1.e-15:
            universe = \
               MMTK.OrthorhombicPeriodicUniverse((e1.length(),
                                                  e2.length(),
                                                  e3.length()))
        else:
            universe = MMTK.ParallelepipedicPeriodicUniverse((e1, e2, e3))
        return universe

    def retrieveAsymmetricUnit(self):
        """
        Constructs a universe (OrthrhombicPeriodicUniverse or
        ParallelepipedicPeriodicUniverse) representing the
        unit cell of the crystal and adds the molecules representing
        the asymmetric unit.
        
        @returns: a universe
        @rtype: L{MMTK.Universe.Universe}
        """
        universe = self.retrieveUniverse()
        universe.addObject(self.retrieveMolecules())
        return universe

    def retrieveUnitCell(self, compact=True):
        """
        Constructs a universe (OrthrhombicPeriodicUniverse or
        ParallelepipedicPeriodicUniverse) representing the
        unit cell of the crystal and adds all the molecules it
        contains, i.e. the molecules of the asymmetric unit and
        its images obtained by applying the crystallographic
        symmetry operations.

        @param compact: if C{True}, the images are shifted such that
                        their centers of mass lie inside the unit cell.
        @type compact: C{bool}
        @returns: a universe
        @rtype: L{MMTK.Universe.Universe}
        """
        universe = self.retrieveUniverse()
        for symop in self.pdb_conf.cs_transformations:
            rotation = symop.asLinearTransformation().tensor
            print rotation
            asu = MMTK.Collection(self.retrieveMolecules())
            for atom in asu.atomList():
                atom.setPosition(symop(atom.position()))
                if hasattr(atom, 'u'):
                    atom.u = rotation.dot(atom.u.dot(rotation.transpose()))
            if compact:
                cm = asu.centerOfMass()
                cm_fr = self.pdb_conf.to_fractional(cm)
                cm_fr = Vector(cm_fr[0] % 1., cm_fr[1] % 1., cm_fr[2] % 1.) \
                        - Vector(0.5, 0.5, 0.5)
                cm = self.pdb_conf.from_fractional(cm_fr)
                asu.translateTo(cm)
            universe.addObject(asu)
        return universe

    def makeAll(self):
        cystines = []
        for chain in self.pdb_conf.peptide_chains:
            chain_id = chain.chain_id
            if not chain_id:
                chain_id = 'PeptideChain'+str(len(self.peptide_chains)+1)
            for residue in chain:
                if residue.name == 'CYS' and residue.atoms.has_key('SG'):
                    cystines.append((chain_id, residue, residue.atoms['SG']))
            self.makeChain(chain, chain_id)
            self.peptide_chains.append(chain_id)
        for i in range(len(cystines)):
            for j in range(i+1, len(cystines)):
                d = (cystines[i][2].position-cystines[j][2].position).length()
                if d < 0.25:
                    if cystines[i][0] is cystines[j][0]:
                        cys1 = cystines[i][1]
                        cys2 = cystines[j][1]
                        cys1 = cys1.name + '_' + str(cys1.number)
                        cys2 = cys2.name + '_' + str(cys2.number)
                        self.addBond(cystines[i][0], cys1+'.SG', cys2+'.SG')
                    else:
                        raise NotImplemented('Inter-chain disulfide bridges'
                                             ' not yet implemented')
        for chain in self.pdb_conf.nucleotide_chains:
            chain_id = chain.chain_id
            if not chain_id:
                chain_id = 'NucleotideChain'+str(len(self.nucleotide_chains)+1)
            self.makeChain(chain, chain_id)
            self.nucleotide_chains.append(chain_id)
        for molname, mollist in self.pdb_conf.molecules.items():
            self.molecules[molname] = []
            for residue in mollist:
                resname = residue.name + '_' + str(residue.number)
                self.makeResidue(residue, resname)
                self.molecules[molname].append(resname)

    def makeChain(self, chain, chain_id):
        groups = []
        for residue in chain:
            resname = chain_id + '_' + residue.name + '_' + str(residue.number)
            groups.append(resname)
            self.makeResidue(residue, resname)
        self.createGroup(chain_id)
        local_resnames = []
        for resname in groups:
            local_resname = '_'.join(resname.split('_')[1:])
            self.addSubgroup(chain_id, local_resname, resname)
            local_resnames.append(local_resname)
        self.setAttribute(chain_id, 'sequence', local_resnames)
        for i in range(1, len(chain)):
            if chain[i-1].number == chain[i].number-1:
                if chain[i-1].atoms.has_key('C') and \
                       chain[i].atoms.has_key('N'):
                    # Peptide chain
                    self.addBond(chain_id, local_resnames[i-1]+'.C',
                                 local_resnames[i]+'.N')
                elif chain[i-1].atoms.has_key('O3*') and \
                         chain[i].atoms.has_key('P'):
                    # Nucleotide chain
                    self.addBond(chain_id, local_resnames[i-1]+'.O3*',
                                 local_resnames[i]+'.P')

    def makeResidue(self, residue, group_name):
        self.createGroup(group_name)
        atoms = []
        for atom in residue:
            atoms.append((atom.name, atom.properties['element'],
                          atom.position))
            self.addAtom(group_name, atom.name, atom.properties['element'])
            self.setPosition(group_name, atom.name, atom.position)
            self.setAttribute(group_name, atom.name+'.temperature_factor',
                              atom.properties['temperature_factor'])
            self.setAttribute(group_name, atom.name+'.serial_number',
                              atom.properties['serial_number'])
            if atom.properties.has_key('u'):
                self.setAttribute(group_name, atom.name+'.u',
                                  atom.properties['u'])
        for i in range(len(atoms)):
            atom_i, element_i, pos_i = atoms[i]
            for j in range(i+1, len(atoms)):
                atom_j, element_j, pos_j = atoms[j]
                if self.assumeBond(element_i, pos_i, element_j, pos_j):
                    self.addBond(group_name, atom_i, atom_j)

    def assumeBond(self, element1, pos1, element2, pos2):
        if element1 > element2:
            element1, element2 = element2, element1
        try:
            d = self.bond_lengths[(element1, element2)]
            return (pos1-pos2).length() < d
        except KeyError:
            return False

    bond_lengths = {('C', 'C'): 0.16,
                    ('C', 'H'): 0.115,
                    ('C', 'N'): 0.215,
                    ('C', 'O'): 0.16,
                    ('C', 'P'): 0.2,
                    ('C', 'S'): 0.2,
                    ('H', 'H'): 0.08,
                    ('H', 'N'): 0.115,
                    ('H', 'O'): 0.115,
                    ('H', 'P'): 0.15,
                    ('H', 'S'): 0.14,
                    ('N', 'N'): 0.155,
                    ('N', 'O'): 0.15,
                    ('O', 'O'): 0.16,
                    ('O', 'P'): 0.17,
                    ('O', 'S'): 0.16,
                    ('P', 'S'): 0.2,
                    ('S', 'S'): 0.25,
                    }
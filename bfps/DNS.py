#######################################################################
#                                                                     #
#  Copyright 2015 Max Planck Institute                                #
#                 for Dynamics and Self-Organization                  #
#                                                                     #
#  This file is part of bfps.                                         #
#                                                                     #
#  bfps is free software: you can redistribute it and/or modify       #
#  it under the terms of the GNU General Public License as published  #
#  by the Free Software Foundation, either version 3 of the License,  #
#  or (at your option) any later version.                             #
#                                                                     #
#  bfps is distributed in the hope that it will be useful,            #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of     #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the      #
#  GNU General Public License for more details.                       #
#                                                                     #
#  You should have received a copy of the GNU General Public License  #
#  along with bfps.  If not, see <http://www.gnu.org/licenses/>       #
#                                                                     #
# Contact: Cristian.Lalescu@ds.mpg.de                                 #
#                                                                     #
#######################################################################



import os
import sys
import shutil
import subprocess
import argparse
import h5py
import math
import numpy as np
import warnings

import bfps
from ._code import _code
from bfps import tools

class DNS(_code):
    """This class is meant to stitch together the C++ code into a final source file,
    compile it, and handle all job launching.
    """
    def __init__(
            self,
            work_dir = './',
            simname = 'test'):
        _code.__init__(
                self,
                work_dir = work_dir,
                simname = simname)
        self.host_info = {'type'        : 'cluster',
                          'environment' : None,
                          'deltanprocs' : 1,
                          'queue'       : '',
                          'mail_address': '',
                          'mail_events' : None}
        self.generate_default_parameters()
        return None
    def set_precision(
            self,
            fluid_dtype):
        if fluid_dtype in [np.float32, np.float64]:
            self.fluid_dtype = fluid_dtype
        elif fluid_dtype in ['single', 'double']:
            if fluid_dtype == 'single':
                self.fluid_dtype = np.dtype(np.float32)
            elif fluid_dtype == 'double':
                self.fluid_dtype = np.dtype(np.float64)
        self.rtype = self.fluid_dtype
        if self.rtype == np.float32:
            self.ctype = np.dtype(np.complex64)
            self.C_field_dtype = 'float'
            self.fluid_precision = 'single'
        elif self.rtype == np.float64:
            self.ctype = np.dtype(np.complex128)
            self.C_field_dtype = 'double'
            self.fluid_precision = 'double'
        return None
    def write_src(self):
        self.version_message = (
                '/***********************************************************************\n' +
                '* this code automatically generated by bfps\n' +
                '* version {0}\n'.format(bfps.__version__) +
                '***********************************************************************/\n\n\n')
        self.include_list = [
                '"base.hpp"',
                '"scope_timer.hpp"',
                '"fftw_interface.hpp"',
                '"full_code/main_code.hpp"',
                '<cmath>',
                '<iostream>',
                '<hdf5.h>',
                '<string>',
                '<cstring>',
                '<fftw3-mpi.h>',
                '<omp.h>',
                '<cfenv>',
                '<cstdlib>',
                '"full_code/{0}.hpp"\n'.format(self.dns_type)]
        self.main = """
            int main(int argc, char *argv[])
            {{
                bool fpe = (
                    (getenv("BFPS_FPE_OFF") == nullptr) ||
                    (getenv("BFPS_FPE_OFF") != std::string("TRUE")));
                return main_code< {0} >(argc, argv, fpe);
            }}
            """.format(self.dns_type + '<{0}>'.format(self.C_field_dtype))
        self.includes = '\n'.join(
                ['#include ' + hh
                 for hh in self.include_list])
        with open(self.name + '.cpp', 'w') as outfile:
            outfile.write(self.version_message + '\n\n')
            outfile.write(self.includes + '\n\n')
            outfile.write(self.cread_pars(
                template_class = '{0}<rnumber>::'.format(self.dns_type),
                template_prefix = 'template <typename rnumber> ',
                simname_variable = 'simname.c_str()') + '\n\n')
            for rnumber in ['float', 'double']:
                outfile.write(self.cread_pars(
                    template_class = '{0}<{1}>::'.format(self.dns_type, rnumber),
                    template_prefix = 'template '.format(rnumber),
                    just_declaration = True) + '\n\n')
            outfile.write(self.main + '\n')
        return None
    def generate_default_parameters(self):
        # these parameters are relevant for all DNS classes
        self.parameters['dealias_type'] = int(1)
        self.parameters['dkx'] = float(1.0)
        self.parameters['dky'] = float(1.0)
        self.parameters['dkz'] = float(1.0)
        self.parameters['niter_todo'] = int(8)
        self.parameters['niter_stat'] = int(1)
        self.parameters['niter_out'] = int(8)
        self.parameters['checkpoints_per_file'] = int(1)
        self.parameters['dt'] = float(0.01)
        self.parameters['nu'] = float(0.1)
        self.parameters['fmode'] = int(1)
        self.parameters['famplitude'] = float(0.5)
        self.parameters['fk0'] = float(2.0)
        self.parameters['fk1'] = float(4.0)
        self.parameters['forcing_type'] = 'linear'
        self.parameters['histogram_bins'] = int(256)
        self.parameters['max_velocity_estimate'] = float(1)
        self.parameters['max_vorticity_estimate'] = float(1)
        # parameters specific to particle version
        self.NSVEp_extra_parameters = {}
        self.NSVEp_extra_parameters['niter_part'] = int(1)
        self.NSVEp_extra_parameters['nparticles'] = int(10)
        self.NSVEp_extra_parameters['tracers0_integration_steps'] = int(4)
        self.NSVEp_extra_parameters['tracers0_neighbours'] = int(1)
        self.NSVEp_extra_parameters['tracers0_smoothness'] = int(1)
        return None
    def get_kspace(self):
        kspace = {}
        if self.parameters['dealias_type'] == 1:
            kMx = self.parameters['dkx']*(self.parameters['nx']//2 - 1)
            kMy = self.parameters['dky']*(self.parameters['ny']//2 - 1)
            kMz = self.parameters['dkz']*(self.parameters['nz']//2 - 1)
        else:
            kMx = self.parameters['dkx']*(self.parameters['nx']//3 - 1)
            kMy = self.parameters['dky']*(self.parameters['ny']//3 - 1)
            kMz = self.parameters['dkz']*(self.parameters['nz']//3 - 1)
        kspace['kM'] = max(kMx, kMy, kMz)
        kspace['dk'] = min(self.parameters['dkx'],
                           self.parameters['dky'],
                           self.parameters['dkz'])
        nshells = int(kspace['kM'] / kspace['dk']) + 2
        kspace['nshell'] = np.zeros(nshells, dtype = np.int64)
        kspace['kshell'] = np.zeros(nshells, dtype = np.float64)
        kspace['kx'] = np.arange( 0,
                                  self.parameters['nx']//2 + 1).astype(np.float64)*self.parameters['dkx']
        kspace['ky'] = np.arange(-self.parameters['ny']//2 + 1,
                                  self.parameters['ny']//2 + 1).astype(np.float64)*self.parameters['dky']
        kspace['ky'] = np.roll(kspace['ky'], self.parameters['ny']//2+1)
        kspace['kz'] = np.arange(-self.parameters['nz']//2 + 1,
                                  self.parameters['nz']//2 + 1).astype(np.float64)*self.parameters['dkz']
        kspace['kz'] = np.roll(kspace['kz'], self.parameters['nz']//2+1)
        return kspace
    def get_data_file_name(self):
        return os.path.join(self.work_dir, self.simname + '.h5')
    def get_data_file(self):
        return h5py.File(self.get_data_file_name(), 'r')
    def get_particle_file_name(self):
        return os.path.join(self.work_dir, self.simname + '_particles.h5')
    def get_particle_file(self):
        return h5py.File(self.get_particle_file_name(), 'r')
    def get_postprocess_file_name(self):
        return os.path.join(self.work_dir, self.simname + '_postprocess.h5')
    def get_postprocess_file(self):
        return h5py.File(self.get_postprocess_file_name(), 'r')
    def compute_statistics(self, iter0 = 0, iter1 = None):
        """Run basic postprocessing on raw data.
        The energy spectrum :math:`E(t, k)` and the enstrophy spectrum
        :math:`\\frac{1}{2}\omega^2(t, k)` are computed from the

        .. math::

            \sum_{k \\leq \\|\\mathbf{k}\\| \\leq k+dk}\\hat{u_i} \\hat{u_j}^*, \\hskip .5cm
            \sum_{k \\leq \\|\\mathbf{k}\\| \\leq k+dk}\\hat{\omega_i} \\hat{\\omega_j}^*

        tensors, and the enstrophy spectrum is also used to
        compute the dissipation :math:`\\varepsilon(t)`.
        These basic quantities are stored in a newly created HDF5 file,
        ``simname_postprocess.h5``.
        """
        if len(list(self.statistics.keys())) > 0:
            return None
        self.read_parameters()
        with self.get_data_file() as data_file:
            if 'moments' not in data_file['statistics'].keys():
                return None
            iter0 = min((data_file['statistics/moments/velocity'].shape[0] *
                         self.parameters['niter_stat']-1),
                        iter0)
            if type(iter1) == type(None):
                iter1 = data_file['iteration'].value
            else:
                iter1 = min(data_file['iteration'].value, iter1)
            ii0 = iter0 // self.parameters['niter_stat']
            ii1 = iter1 // self.parameters['niter_stat']
            self.statistics['kshell'] = data_file['kspace/kshell'].value
            self.statistics['kM'] = data_file['kspace/kM'].value
            self.statistics['dk'] = data_file['kspace/dk'].value
            computation_needed = True
            pp_file = h5py.File(self.get_postprocess_file_name(), 'a')
            if 'ii0' in pp_file.keys():
                computation_needed =  not (ii0 == pp_file['ii0'].value and
                                           ii1 == pp_file['ii1'].value)
                if computation_needed:
                    for k in pp_file.keys():
                        del pp_file[k]
            if computation_needed:
                pp_file['iter0'] = iter0
                pp_file['iter1'] = iter1
                pp_file['ii0'] = ii0
                pp_file['ii1'] = ii1
                pp_file['t'] = (self.parameters['dt']*
                                self.parameters['niter_stat']*
                                (np.arange(ii0, ii1+1).astype(np.float)))
                pp_file['energy(t, k)'] = (
                    data_file['statistics/spectra/velocity_velocity'][ii0:ii1+1, :, 0, 0] +
                    data_file['statistics/spectra/velocity_velocity'][ii0:ii1+1, :, 1, 1] +
                    data_file['statistics/spectra/velocity_velocity'][ii0:ii1+1, :, 2, 2])/2
                pp_file['enstrophy(t, k)'] = (
                    data_file['statistics/spectra/vorticity_vorticity'][ii0:ii1+1, :, 0, 0] +
                    data_file['statistics/spectra/vorticity_vorticity'][ii0:ii1+1, :, 1, 1] +
                    data_file['statistics/spectra/vorticity_vorticity'][ii0:ii1+1, :, 2, 2])/2
                pp_file['vel_max(t)'] = data_file['statistics/moments/velocity']  [ii0:ii1+1, 9, 3]
                pp_file['renergy(t)'] = data_file['statistics/moments/velocity'][ii0:ii1+1, 2, 3]/2
            for k in ['t',
                      'energy(t, k)',
                      'enstrophy(t, k)',
                      'vel_max(t)',
                      'renergy(t)']:
                if k in pp_file.keys():
                    self.statistics[k] = pp_file[k].value
            self.compute_time_averages()
        return None
    def compute_time_averages(self):
        """Compute easy stats.

        Further computation of statistics based on the contents of
        ``simname_postprocess.h5``.
        Standard quantities are as follows
        (consistent with [Ishihara]_):

        .. math::

            U_{\\textrm{int}}(t) = \\sqrt{\\frac{2E(t)}{3}}, \\hskip .5cm
            L_{\\textrm{int}}(t) = \\frac{\pi}{2U_{int}^2(t)} \\int \\frac{dk}{k} E(t, k), \\hskip .5cm
            T_{\\textrm{int}}(t) =
            \\frac{L_{\\textrm{int}}(t)}{U_{\\textrm{int}}(t)}

            \\eta_K = \\left(\\frac{\\nu^3}{\\varepsilon}\\right)^{1/4}, \\hskip .5cm
            \\tau_K = \\left(\\frac{\\nu}{\\varepsilon}\\right)^{1/2}, \\hskip .5cm
            \\lambda = \\sqrt{\\frac{15 \\nu U_{\\textrm{int}}^2}{\\varepsilon}}

            Re = \\frac{U_{\\textrm{int}} L_{\\textrm{int}}}{\\nu}, \\hskip
            .5cm
            R_{\\lambda} = \\frac{U_{\\textrm{int}} \\lambda}{\\nu}

        .. [Ishihara] T. Ishihara et al,
                      *Small-scale statistics in high-resolution direct numerical
                      simulation of turbulence: Reynolds number dependence of
                      one-point velocity gradient statistics*.
                      J. Fluid Mech.,
                      **592**, 335-366, 2007
        """
        for key in ['energy', 'enstrophy']:
            self.statistics[key + '(t)'] = (self.statistics['dk'] *
                                            np.sum(self.statistics[key + '(t, k)'], axis = 1))
        self.statistics['Uint(t)'] = np.sqrt(2*self.statistics['energy(t)'] / 3)
        self.statistics['Lint(t)'] = ((self.statistics['dk']*np.pi /
                                       (2*self.statistics['Uint(t)']**2)) *
                                      np.nansum(self.statistics['energy(t, k)'] /
                                                self.statistics['kshell'][None, :], axis = 1))
        for key in ['energy',
                    'enstrophy',
                    'vel_max',
                    'Uint',
                    'Lint']:
            if key + '(t)' in self.statistics.keys():
                self.statistics[key] = np.average(self.statistics[key + '(t)'], axis = 0)
        for suffix in ['', '(t)']:
            self.statistics['diss'    + suffix] = (self.parameters['nu'] *
                                                   self.statistics['enstrophy' + suffix]*2)
            self.statistics['etaK'    + suffix] = (self.parameters['nu']**3 /
                                                   self.statistics['diss' + suffix])**.25
            self.statistics['tauK'    + suffix] =  (self.parameters['nu'] /
                                                    self.statistics['diss' + suffix])**.5
            self.statistics['Re' + suffix] = (self.statistics['Uint' + suffix] *
                                              self.statistics['Lint' + suffix] /
                                              self.parameters['nu'])
            self.statistics['lambda' + suffix] = (15 * self.parameters['nu'] *
                                                  self.statistics['Uint' + suffix]**2 /
                                                  self.statistics['diss' + suffix])**.5
            self.statistics['Rlambda' + suffix] = (self.statistics['Uint' + suffix] *
                                                   self.statistics['lambda' + suffix] /
                                                   self.parameters['nu'])
            self.statistics['kMeta' + suffix] = (self.statistics['kM'] *
                                                 self.statistics['etaK' + suffix])
            if self.parameters['dealias_type'] == 1:
                self.statistics['kMeta' + suffix] *= 0.8
        self.statistics['Tint'] = self.statistics['Lint'] / self.statistics['Uint']
        self.statistics['Taylor_microscale'] = self.statistics['lambda']
        return None
    def set_plt_style(
            self,
            style = {'dashes' : (None, None)}):
        self.style.update(style)
        return None
    def convert_complex_from_binary(
            self,
            field_name = 'vorticity',
            iteration = 0,
            file_name = None):
        """read the Fourier representation of a vector field.

        Read the binary file containing iteration ``iteration`` of the
        field ``field_name``, and write it in a ``.h5`` file.
        """
        data = np.memmap(
                os.path.join(self.work_dir,
                             self.simname + '_{0}_i{1:0>5x}'.format('c' + field_name, iteration)),
                dtype = self.ctype,
                mode = 'r',
                shape = (self.parameters['ny'],
                         self.parameters['nz'],
                         self.parameters['nx']//2+1,
                         3))
        if type(file_name) == type(None):
            file_name = self.simname + '_{0}_i{1:0>5x}.h5'.format('c' + field_name, iteration)
            file_name = os.path.join(self.work_dir, file_name)
        f = h5py.File(file_name, 'a')
        f[field_name + '/complex/{0}'.format(iteration)] = data
        f.close()
        return None
    def write_par(
            self,
            iter0 = 0,
            particle_ic = None):
        assert (self.parameters['niter_todo'] % self.parameters['niter_stat'] == 0)
        assert (self.parameters['niter_todo'] % self.parameters['niter_out']  == 0)
        assert (self.parameters['niter_out']  % self.parameters['niter_stat'] == 0)
        if self.dns_type == 'NSVEp':
            assert (self.parameters['niter_todo'] % self.parameters['niter_part'] == 0)
            assert (self.parameters['niter_out']  % self.parameters['niter_part'] == 0)
        _code.write_par(self, iter0 = iter0)
        with h5py.File(self.get_data_file_name(), 'r+') as ofile:
            ofile['bfps_info/exec_name'] = self.name
            kspace = self.get_kspace()
            for k in kspace.keys():
                ofile['kspace/' + k] = kspace[k]
            nshells = kspace['nshell'].shape[0]
            kspace = self.get_kspace()
            nshells = kspace['nshell'].shape[0]
            vec_stat_datasets = ['velocity', 'vorticity']
            scal_stat_datasets = []
            for k in vec_stat_datasets:
                time_chunk = 2**20//(8*3*3*nshells)
                time_chunk = max(time_chunk, 1)
                ofile.create_dataset('statistics/spectra/' + k + '_' + k,
                                     (1, nshells, 3, 3),
                                     chunks = (time_chunk, nshells, 3, 3),
                                     maxshape = (None, nshells, 3, 3),
                                     dtype = np.float64)
                time_chunk = 2**20//(8*4*10)
                time_chunk = max(time_chunk, 1)
                a = ofile.create_dataset('statistics/moments/' + k,
                                     (1, 10, 4),
                                     chunks = (time_chunk, 10, 4),
                                     maxshape = (None, 10, 4),
                                     dtype = np.float64)
                time_chunk = 2**20//(8*4*self.parameters['histogram_bins'])
                time_chunk = max(time_chunk, 1)
                ofile.create_dataset('statistics/histograms/' + k,
                                     (1,
                                      self.parameters['histogram_bins'],
                                      4),
                                     chunks = (time_chunk,
                                               self.parameters['histogram_bins'],
                                               4),
                                     maxshape = (None,
                                                 self.parameters['histogram_bins'],
                                                 4),
                                     dtype = np.int64)
            ofile['checkpoint'] = int(0)
        if self.dns_type == 'NSVE':
            return None

        if type(particle_ic) == type(None):
            pbase_shape = (self.parameters['nparticles'],)
            number_of_particles = self.parameters['nparticles']
        else:
            pbase_shape = particle_ic.shape[:-1]
            assert(particle_ic.shape[-1] == 3)
            number_of_particles = 1
            for val in pbase_shape[1:]:
                number_of_particles *= val
        with h5py.File(self.get_checkpoint_0_fname(), 'a') as ofile:
            s = 0
            ofile.create_group('tracers{0}'.format(s))
            ofile.create_group('tracers{0}/rhs'.format(s))
            ofile.create_group('tracers{0}/state'.format(s))
            ofile['tracers{0}/rhs'.format(s)].create_dataset(
                    '0',
                    shape = (
                        (self.parameters['tracers{0}_integration_steps'.format(s)],) +
                        pbase_shape +
                        (3,)),
                    dtype = np.float)
            ofile['tracers{0}/state'.format(s)].create_dataset(
                    '0',
                    shape = (
                        pbase_shape +
                        (3,)),
                    dtype = np.float)
        return None
    def job_parser_arguments(
            self,
            parser):
        parser.add_argument(
                '--ncpu',
                type = int,
                dest = 'ncpu',
                default = -1)
        parser.add_argument(
                '--np', '--nprocesses',
                metavar = 'NPROCESSES',
                help = 'number of mpi processes to use',
                type = int,
                dest = 'nb_processes',
                default = 4)
        parser.add_argument(
                '--ntpp', '--nthreads-per-process',
                type = int,
                dest = 'nb_threads_per_process',
                metavar = 'NTHREADS_PER_PROCESS',
                help = 'number of threads to use per MPI process',
                default = 1)
        parser.add_argument(
                '--no-submit',
                action = 'store_true',
                dest = 'no_submit')
        parser.add_argument(
                '--environment',
                type = str,
                dest = 'environment',
                default = None)
        parser.add_argument(
                '--minutes',
                type = int,
                dest = 'minutes',
                default = 5,
                help = 'If environment supports it, this is the requested wall-clock-limit.')
        parser.add_argument(
               '--njobs',
               type = int, dest = 'njobs',
               default = 1)
        return None
    def simulation_parser_arguments(
            self,
            parser):
        parser.add_argument(
                '--simname',
                type = str, dest = 'simname',
                default = 'test')
        parser.add_argument(
               '-n', '--cube-size',
               type = int,
               dest = 'n',
               default = 32,
               metavar = 'N',
               help = 'code is run by default in a grid of NxNxN')
        parser.add_argument(
                '--wd',
                type = str, dest = 'work_dir',
                default = './')
        parser.add_argument(
                '--precision',
                choices = ['single', 'double'],
                type = str,
                default = 'single')
        parser.add_argument(
                '--src-wd',
                type = str,
                dest = 'src_work_dir',
                default = '')
        parser.add_argument(
                '--src-simname',
                type = str,
                dest = 'src_simname',
                default = '')
        parser.add_argument(
                '--src-iteration',
                type = int,
                dest = 'src_iteration',
                default = 0)
        parser.add_argument(
               '--kMeta',
               type = float,
               dest = 'kMeta',
               default = 2.0)
        parser.add_argument(
               '--dtfactor',
               type = float,
               dest = 'dtfactor',
               default = 0.5,
               help = 'dt is computed as DTFACTOR / N')
        return None
    def particle_parser_arguments(
            self,
            parser):
        parser.add_argument(
               '--particle-rand-seed',
               type = int,
               dest = 'particle_rand_seed',
               default = None)
        parser.add_argument(
               '--pclouds',
               type = int,
               dest = 'pclouds',
               default = 1,
               help = ('number of particle clouds. Particle "clouds" '
                       'consist of particles distributed according to '
                       'pcloud-type.'))
        parser.add_argument(
                '--pcloud-type',
                choices = ['random-cube',
                           'regular-cube'],
                dest = 'pcloud_type',
                default = 'random-cube')
        parser.add_argument(
               '--particle-cloud-size',
               type = float,
               dest = 'particle_cloud_size',
               default = 2*np.pi)
        parser.add_argument(
                '--neighbours',
                type = int,
                dest = 'neighbours',
                default = 1)
        parser.add_argument(
                '--smoothness',
                type = int,
                dest = 'smoothness',
                default = 1)
        return None
    def add_parser_arguments(
            self,
            parser):
        subparsers = parser.add_subparsers(
                dest = 'DNS_class',
                help = 'type of simulation to run')
        subparsers.required = True
        parser_NSVE = subparsers.add_parser(
                'NSVE',
                help = 'plain Navier-Stokes vorticity formulation')
        self.simulation_parser_arguments(parser_NSVE)
        self.job_parser_arguments(parser_NSVE)
        self.parameters_to_parser_arguments(parser_NSVE)

        parser_NSVEp = subparsers.add_parser(
                'NSVEp',
                help = 'plain Navier-Stokes vorticity formulation, with basic fluid tracers')
        self.simulation_parser_arguments(parser_NSVEp)
        self.job_parser_arguments(parser_NSVEp)
        self.particle_parser_arguments(parser_NSVEp)
        self.parameters_to_parser_arguments(parser_NSVEp)
        self.parameters_to_parser_arguments(
                parser_NSVEp,
                self.NSVEp_extra_parameters)
        return None
    def prepare_launch(
            self,
            args = []):
        """Set up reasonable parameters.

        With the default Lundgren forcing applied in the band [2, 4],
        we can estimate the dissipation, therefore we can estimate
        :math:`k_M \\eta_K` and constrain the viscosity.

        In brief, the command line parameter :math:`k_M \\eta_K` is
        used in the following formula for :math:`\\nu` (:math:`N` is the
        number of real space grid points per coordinate):

        .. math::

            \\nu = \\left(\\frac{2 k_M \\eta_K}{N} \\right)^{4/3}

        With this choice, the average dissipation :math:`\\varepsilon`
        will be close to 0.4, and the integral scale velocity will be
        close to 0.77, yielding the approximate value for the Taylor
        microscale and corresponding Reynolds number:

        .. math::

            \\lambda \\approx 4.75\\left(\\frac{2 k_M \\eta_K}{N} \\right)^{4/6}, \\hskip .5in
            R_\\lambda \\approx 3.7 \\left(\\frac{N}{2 k_M \\eta_K} \\right)^{4/6}

        """
        opt = _code.prepare_launch(self, args = args)
        self.set_precision(opt.precision)
        self.dns_type = opt.DNS_class
        self.name = self.dns_type + '-' + self.fluid_precision + '-v' + bfps.__version__
        # merge parameters if needed
        if self.dns_type == 'NSVEp':
            for k in self.NSVEp_extra_parameters.keys():
                self.parameters[k] = self.NSVEp_extra_parameters[k]
        self.parameters['nu'] = (opt.kMeta * 2 / opt.n)**(4./3)
        self.parameters['dt'] = (opt.dtfactor / opt.n)
        # custom famplitude for 288 and 576
        if opt.n == 288:
            self.parameters['famplitude'] = 0.45
        elif opt.n == 576:
            self.parameters['famplitude'] = 0.47
        if ((self.parameters['niter_todo'] % self.parameters['niter_out']) != 0):
            self.parameters['niter_out'] = self.parameters['niter_todo']
        if len(opt.src_work_dir) == 0:
            opt.src_work_dir = os.path.realpath(opt.work_dir)
        self.pars_from_namespace(opt)
        return opt
    def launch(
            self,
            args = [],
            **kwargs):
        opt = self.prepare_launch(args = args)
        self.launch_jobs(opt = opt, **kwargs)
        return None
    def get_checkpoint_0_fname(self):
        return os.path.join(
                    self.work_dir,
                    self.simname + '_checkpoint_0.h5')
    def generate_tracer_state(
            self,
            rseed = None,
            iteration = 0,
            species = 0,
            write_to_file = False,
            ncomponents = 3,
            testing = False,
            data = None):
        if (type(data) == type(None)):
            if not type(rseed) == type(None):
                np.random.seed(rseed)
            #point with problems: 5.37632864e+00,   6.10414710e+00,   6.25256493e+00]
            data = np.zeros(self.parameters['nparticles']*ncomponents).reshape(-1, ncomponents)
            data[:, :3] = np.random.random((self.parameters['nparticles'], 3))*2*np.pi
        if testing:
            #data[0] = np.array([3.26434, 4.24418, 3.12157])
            data[:] = np.array([ 0.72086101,  2.59043666,  6.27501953])
        with h5py.File(self.get_checkpoint_0_fname(), 'a') as data_file:
            data_file['tracers{0}/state/0'.format(species)][:] = data
        if write_to_file:
            data.tofile(
                    os.path.join(
                        self.work_dir,
                        "tracers{0}_state_i{1:0>5x}".format(species, iteration)))
        return data
    def generate_vector_field(
            self,
            rseed = 7547,
            spectra_slope = 1.,
            amplitude = 1.,
            iteration = 0,
            field_name = 'vorticity',
            write_to_file = False,
            # to switch to constant field, use generate_data_3D_uniform
            # for scalar_generator
            scalar_generator = tools.generate_data_3D):
        """generate vector field.

        The generated field is not divergence free, but it has the proper
        shape.

        :param rseed: seed for random number generator
        :param spectra_slope: spectrum of field will look like k^(-p)
        :param amplitude: all amplitudes are multiplied with this value
        :param iteration: the field is written at this iteration
        :param field_name: the name of the field being generated
        :param write_to_file: should we write the field to file?
        :param scalar_generator: which function to use for generating the
            individual components.
            Possible values: bfps.tools.generate_data_3D,
            bfps.tools.generate_data_3D_uniform
        :type rseed: int
        :type spectra_slope: float
        :type amplitude: float
        :type iteration: int
        :type field_name: str
        :type write_to_file: bool
        :type scalar_generator: function

        :returns: ``Kdata``, a complex valued 4D ``numpy.array`` that uses the
            transposed FFTW layout.
            Kdata[ky, kz, kx, i] is the amplitude of mode (kx, ky, kz) for
            the i-th component of the field.
            (i.e. x is the fastest index and z the slowest index in the
            real-space representation).
        """
        np.random.seed(rseed)
        Kdata00 = scalar_generator(
                self.parameters['nz']//2,
                self.parameters['ny']//2,
                self.parameters['nx']//2,
                p = spectra_slope,
                amplitude = amplitude).astype(self.ctype)
        Kdata01 = scalar_generator(
                self.parameters['nz']//2,
                self.parameters['ny']//2,
                self.parameters['nx']//2,
                p = spectra_slope,
                amplitude = amplitude).astype(self.ctype)
        Kdata02 = scalar_generator(
                self.parameters['nz']//2,
                self.parameters['ny']//2,
                self.parameters['nx']//2,
                p = spectra_slope,
                amplitude = amplitude).astype(self.ctype)
        Kdata0 = np.zeros(
                Kdata00.shape + (3,),
                Kdata00.dtype)
        Kdata0[..., 0] = Kdata00
        Kdata0[..., 1] = Kdata01
        Kdata0[..., 2] = Kdata02
        Kdata1 = tools.padd_with_zeros(
                Kdata0,
                self.parameters['nz'],
                self.parameters['ny'],
                self.parameters['nx'])
        if write_to_file:
            Kdata1.tofile(
                    os.path.join(self.work_dir,
                                 self.simname + "_c{0}_i{1:0>5x}".format(field_name, iteration)))
        return Kdata1
    def launch_jobs(
            self,
            opt = None,
            particle_initial_condition = None):
        if not os.path.exists(os.path.join(self.work_dir, self.simname + '.h5')):
            # take care of fields' initial condition
            if not os.path.exists(self.get_checkpoint_0_fname()):
                f = h5py.File(self.get_checkpoint_0_fname(), 'w')
                if len(opt.src_simname) > 0:
                    source_cp = 0
                    src_file = 'not_a_file'
                    while True:
                        src_file = os.path.join(
                            os.path.realpath(opt.src_work_dir),
                            opt.src_simname + '_checkpoint_{0}.h5'.format(source_cp))
                        f0 = h5py.File(src_file, 'r')
                        if '{0}'.format(opt.src_iteration) in f0['vorticity/complex'].keys():
                            f0.close()
                            break
                        source_cp += 1
                    f['vorticity/complex/{0}'.format(0)] = h5py.ExternalLink(
                            src_file,
                            'vorticity/complex/{0}'.format(opt.src_iteration))
                else:
                    data = self.generate_vector_field(
                           write_to_file = False,
                           spectra_slope = 2.0,
                           amplitude = 0.05)
                    f['vorticity/complex/{0}'.format(0)] = data
                f.close()
            # take care of particles' initial condition
            if self.dns_type == 'NSVEp':
                if opt.pclouds > 1:
                    np.random.seed(opt.particle_rand_seed)
                    if opt.pcloud_type == 'random-cube':
                        particle_initial_condition = (
                            np.random.random((opt.pclouds, 1, 3))*2*np.pi +
                            np.random.random((1, self.parameters['nparticles'], 3))*opt.particle_cloud_size)
                    elif opt.pcloud_type == 'regular-cube':
                        onedarray = np.linspace(
                                -opt.particle_cloud_size/2,
                                opt.particle_cloud_size/2,
                                self.parameters['nparticles'])
                        particle_initial_condition = np.zeros(
                                (opt.pclouds,
                                 self.parameters['nparticles'],
                                 self.parameters['nparticles'],
                                 self.parameters['nparticles'], 3),
                                dtype = np.float64)
                        particle_initial_condition[:] = \
                            np.random.random((opt.pclouds, 1, 1, 1, 3))*2*np.pi
                        particle_initial_condition[..., 0] += onedarray[None, None, None, :]
                        particle_initial_condition[..., 1] += onedarray[None, None, :, None]
                        particle_initial_condition[..., 2] += onedarray[None, :, None, None]
            self.write_par(
                    particle_ic = particle_initial_condition)
            if self.dns_type == 'NSVEp':
                if self.parameters['nparticles'] > 0:
                    data = self.generate_tracer_state(
                            species = 0,
                            rseed = opt.particle_rand_seed,
                            data = particle_initial_condition)
        self.run(
                nb_processes = opt.nb_processes,
                nb_threads_per_process = opt.nb_threads_per_process,
                njobs = opt.njobs,
                hours = opt.minutes // 60,
                minutes = opt.minutes % 60,
                no_submit = opt.no_submit)
        return None

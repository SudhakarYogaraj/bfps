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

import bfps
from ._fluid_base import _fluid_particle_base

class FluidResize(_fluid_particle_base):
    """This class is meant to resize snapshots of DNS states to new grids.
    Typical stuff for DNS of turbulence.
    It will become superfluous when HDF5 is used for field I/O.
    """
    def __init__(
            self,
            name = 'FluidResize-v' + bfps.__version__,
            work_dir = './',
            simname = 'test',
            fluid_precision = 'single',
            use_fftw_wisdom = False):
        _fluid_particle_base.__init__(
                self,
                name = name + '-' + fluid_precision,
                work_dir = work_dir,
                simname = simname,
                dtype = fluid_precision,
                use_fftw_wisdom = use_fftw_wisdom)
        self.parameters['src_simname'] = 'test'
        self.parameters['dst_iter'] = 0
        self.parameters['dst_nx'] = 32
        self.parameters['dst_ny'] = 32
        self.parameters['dst_nz'] = 32
        self.parameters['dst_simname'] = 'new_test'
        self.parameters['dst_dkx'] = 1.0
        self.parameters['dst_dky'] = 1.0
        self.parameters['dst_dkz'] = 1.0
        self.fill_up_fluid_code()
        self.finalize_code()
        return None
    def fill_up_fluid_code(self):
        self.fluid_includes += '#include <cstring>\n'
        self.fluid_includes += '#include "fftw_tools.hpp"\n'
        self.fluid_variables += ('double t;\n' +
                                 'fluid_solver<' + self.C_dtype + '> *fs0, *fs1;\n')
        self.fluid_start += """
                //begincpp
                char fname[512];
                fs0 = new fluid_solver<{0}>(
                        src_simname,
                        nx, ny, nz,
                        dkx, dky, dkz);
                fs1 = new fluid_solver<{0}>(
                        dst_simname,
                        dst_nx, dst_ny, dst_nz,
                        dst_dkx, dst_dky, dst_dkz);
                fs0->iteration = iteration;
                fs1->iteration = 0;
                DEBUG_MSG("about to read field\\n");
                fs0->read('v', 'c');
                DEBUG_MSG("field read, about to copy data\\n");
                double a, b;
                fs0->compute_velocity(fs0->cvorticity);
                a = 0.5*fs0->autocorrel(fs0->cvelocity);
                b = 0.5*fs0->autocorrel(fs0->cvorticity);
                DEBUG_MSG("old field %d %g %g\\n", fs0->iteration, a, b);
                copy_complex_array<{0}>(fs0->cd, fs0->cvorticity,
                                        fs1->cd, fs1->cvorticity,
                                        3);
                DEBUG_MSG("data copied, about to write new field\\n");
                fs1->write('v', 'c');
                DEBUG_MSG("finished writing\\n");
                fs1->compute_velocity(fs1->cvorticity);
                a = 0.5*fs1->autocorrel(fs1->cvelocity);
                b = 0.5*fs1->autocorrel(fs1->cvorticity);
                DEBUG_MSG("new field %d %g %g\\n", fs1->iteration, a, b);
                //endcpp
                """.format(self.C_dtype)
        self.fluid_end += """
                //begincpp
                delete fs0;
                delete fs1;
                //endcpp
                """
        return None
    def specific_parser_arguments(
            self,
            parser):
        _fluid_particle_base.specific_parser_arguments(self, parser)
        parser.add_argument(
                '-m',
                type = int,
                dest = 'm',
                default = 32,
                metavar = 'M',
                help = 'resize from N to M')
        parser.add_argument(
                '--src_wd',
                type = str,
                dest = 'src_work_dir',
                required = True)
        parser.add_argument(
                '--src_iteration',
                type = int,
                dest = 'src_iteration',
                required = True)
        return None
    def launch(
            self,
            args = [],
            **kwargs):
        opt = self.prepare_launch(args)
        cmd_line_pars = vars(opt)
        for k in ['dst_nx', 'dst_ny', 'dst_nz']:
            if type(cmd_line_pars[k]) == type(None):
                cmd_line_pars[k] = opt.m
        # the 3 dst_ni have been updated in opt itself at this point
        # I'm not sure if this code is future-proof...
        self.parameters['niter_todo'] = 0
        self.pars_from_namespace(opt)
        src_file = os.path.join(
                os.path.realpath(opt.src_work_dir),
                opt.src_simname + '_cvorticity_i{0:0>5x}'.format(opt.src_iteration))
        read_file = os.path.join(
                self.work_dir,
                opt.src_simname + '_cvorticity_i{0:0>5x}'.format(opt.src_iteration))
        self.write_par(iter0 = opt.src_iteration)
        if not os.path.exists(read_file):
            os.symlink(src_file, read_file)
        self.run(ncpu = opt.ncpu,
                 hours = opt.minutes // 60,
                 minutes = opt.minutes % 60)
        return None


import numpy as np
import h5py
import matplotlib.pyplot as plt
import pyfftw
import bfps
import bfps.tools

import os

from bfps._fluid_base import _fluid_particle_base

class TestField(_fluid_particle_base):
    def __init__(
            self,
            name = 'TestField-v' + bfps.__version__,
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
        self.fill_up_fluid_code()
        self.finalize_code()
        return None
    def fill_up_fluid_code(self):
        self.fluid_includes += '#include <cstring>\n'
        self.fluid_includes += '#include "fftw_tools.hpp"\n'
        self.fluid_includes += '#include "field.hpp"\n'
        self.fluid_variables += ('field<' + self.C_dtype + ', FFTW, ONE> *f;\n' +
                                 'field<' + self.C_dtype + ', FFTW, THREE> *v;\n' +
                                 'kspace<FFTW, SMOOTH> *kk;\n')
        self.fluid_start += """
                //begincpp
                f = new field<{0}, FFTW, ONE>(
                        nx, ny, nz, MPI_COMM_WORLD);
                v = new field<{0}, FFTW, THREE>(
                        nx, ny, nz, MPI_COMM_WORLD);
                kk = new kspace<FFTW, SMOOTH>(
                        f->clayout, 1., 1., 1.);
                // read rdata
                f->real_space_representation = true;
                f->io("field.h5", "scal", 0, true);
                // go to fourier space, write into cdata_tmp
                f->dft();
                f->io("field.h5", "scal_tmp", 0, false);
                f->ift();
                f->io("field.h5", "scal", 0, false);
                f->real_space_representation = false;
                f->io("field.h5", "scal", 0, true);
                hid_t gg;
                if (f->myrank == 0)
                    gg = H5Fopen("field.h5", H5F_ACC_RDWR, H5P_DEFAULT);
                kk->cospectrum<float, ONE>(
                        f->get_cdata(),
                        f->get_cdata(),
                        gg,
                        "scal",
                        0);
                f->ift();
                f->io("field.h5", "scal_tmp", 0, false);
                std::vector<double> me;
                me.resize(1);
                me[0] = 30;
                f->compute_rspace_stats(
                        gg, "scal",
                        0, me);
                if (f->myrank == 0)
                    H5Fclose(gg);
                v->real_space_representation = false;
                v->io("field.h5", "vec", 0, true);
                v->io("field.h5", "vec_tmp", 0, false);
                //endcpp
                """.format(self.C_dtype)
        self.fluid_end += """
                //begincpp
                delete f;
                delete v;
                //endcpp
                """
        return None
    def specific_parser_arguments(
            self,
            parser):
        _fluid_particle_base.specific_parser_arguments(self, parser)
        return None
    def launch(
            self,
            args = [],
            **kwargs):
        opt = self.prepare_launch(args)
        self.parameters['niter_todo'] = 0
        self.pars_from_namespace(opt)
        self.set_host_info(bfps.host_info)
        self.write_par()
        self.run(ncpu = opt.ncpu)
        return None

def main():
    n = 32
    kdata = pyfftw.n_byte_align_empty(
            (n, n, n//2 + 1),
            pyfftw.simd_alignment,
            dtype = np.complex64)
    rdata = pyfftw.n_byte_align_empty(
            (n, n, n),
            pyfftw.simd_alignment,
            dtype = np.float32)
    c2r = pyfftw.FFTW(
            kdata.transpose((1, 0, 2)),
            rdata,
            axes = (0, 1, 2),
            direction = 'FFTW_BACKWARD',
            threads = 2)
    kdata[:] = bfps.tools.generate_data_3D(n, n, n, dtype = np.complex64)
    cdata = kdata.copy()
    c2r.execute()

    tf = TestField()
    tf.parameters['nx'] = n
    tf.parameters['ny'] = n
    tf.parameters['nz'] = n
    f = h5py.File('field.h5', 'w')
    f['scal/complex/0'] = cdata
    f['scal/real/0'] = rdata
    f['vec/complex/0'] = np.array([cdata, cdata, cdata]).reshape(cdata.shape + (3,))
    f['vec/real/0'] = np.array([rdata, rdata, rdata]).reshape(rdata.shape + (3,))
    f['moments/scal'] = np.zeros(shape = (1, 10)).astype(np.float)
    f['histograms/scal'] = np.zeros(shape = (1, 64)).astype(np.float)
    kspace = tf.get_kspace()
    nshells = kspace['nshell'].shape[0]
    f['spectra/scal'] = np.zeros(shape = (1, nshells)).astype(np.float64)
    f.close()

    ## run cpp code
    tf.launch(
            ['-n', '{0}'.format(n),
             '--ncpu', '2'])

    f = h5py.File('field.h5', 'r')
    #err0 = np.max(np.abs(f['scal_tmp/real/0'].value - rdata)) / np.mean(np.abs(rdata))
    #err1 = np.max(np.abs(f['scal/real/0'].value/(n**3) - rdata)) / np.mean(np.abs(rdata))
    #err2 = np.max(np.abs(f['scal_tmp/complex/0'].value/(n**3) - cdata)) / np.mean(np.abs(cdata))
    #print(err0, err1, err2)
    #assert(err0 < 1e-5)
    #assert(err1 < 1e-5)
    #assert(err2 < 1e-4)
    ## compare
    fig = plt.figure(figsize=(18, 6))
    a = fig.add_subplot(131)
    a.set_axis_off()
    v0 = f['vec/complex/0'][:, :, 0, 0]
    v1 = f['vec_tmp/complex/0'][:, :, 0, 0]
    a.imshow(np.log(np.abs(v0 - v1)),
             interpolation = 'none')
    a = fig.add_subplot(132)
    a.set_axis_off()
    a.imshow(np.log(np.abs(v0)),
             interpolation = 'none')
    a = fig.add_subplot(133)
    a.set_axis_off()
    a.imshow(np.log(np.abs(v1)),
             interpolation = 'none')
    fig.tight_layout()
    fig.savefig('tst_fields.pdf')
    fig = plt.figure(figsize=(18, 6))
    a = fig.add_subplot(131)
    a.set_axis_off()
    v0 = f['scal/complex/0'][:, :, 0]
    v1 = f['scal_tmp/complex/0'][:, :, 0]
    a.imshow(np.log(np.abs(v0 - v1)),
             interpolation = 'none')
    a = fig.add_subplot(132)
    a.set_axis_off()
    a.imshow(np.log(np.abs(v0)),
             interpolation = 'none')
    a = fig.add_subplot(133)
    a.set_axis_off()
    a.imshow(np.log(np.abs(v1)),
             interpolation = 'none')
    fig.tight_layout()
    fig.savefig('tst_sfields.pdf')
    # look at moments and histogram
    #print('moments are ', f['moments/scal'][0])
    #fig = plt.figure(figsize=(6,6))
    #a = fig.add_subplot(211)
    #a.plot(f['histograms/scal'][0])
    #a.set_yscale('log')
    #a = fig.add_subplot(212)
    #a.plot(f['spectra/scal'][0])
    #a.set_xscale('log')
    #a.set_yscale('log')
    #fig.tight_layout()
    #fig.savefig('tst.pdf')
    return None

if __name__ == '__main__':
    main()


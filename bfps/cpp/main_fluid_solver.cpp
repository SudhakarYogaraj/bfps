/***********************************************************************
*
*  Copyright 2015 Max Planck Institute for Dynamics and SelfOrganization
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*
* Contact: Cristian.Lalescu@ds.mpg.de
*
************************************************************************/

#include "base.hpp"
#include "fluid_solver.hpp"
#include <iostream>
#include <fftw3-mpi.h>

int myrank, nprocs;

int main(int argc, char *argv[])
{
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &myrank);
    MPI_Comm_size(MPI_COMM_WORLD, &nprocs);

    fluid_solver<float> *fs;
    fs = new fluid_solver<float>(32, 32, 32);
    DEBUG_MSG("fluid_solver object created\n");

    fftwf_execute(*(fftwf_plan*)fs->c2r_vorticity);
    fftwf_execute(*(fftwf_plan*)fs->r2c_vorticity);

    delete fs;
    DEBUG_MSG("fluid_solver object deleted\n");

    // clean up
    fftwf_mpi_cleanup();
    fftw_mpi_cleanup();
    MPI_Finalize();
    return EXIT_SUCCESS;
}

/**********************************************************************
*                                                                     *
*  Copyright 2015 Max Planck Institute                                *
*                 for Dynamics and Self-Organization                  *
*                                                                     *
*  This file is part of bfps.                                         *
*                                                                     *
*  bfps is free software: you can redistribute it and/or modify       *
*  it under the terms of the GNU General Public License as published  *
*  by the Free Software Foundation, either version 3 of the License,  *
*  or (at your option) any later version.                             *
*                                                                     *
*  bfps is distributed in the hope that it will be useful,            *
*  but WITHOUT ANY WARRANTY; without even the implied warranty of     *
*  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the      *
*  GNU General Public License for more details.                       *
*                                                                     *
*  You should have received a copy of the GNU General Public License  *
*  along with bfps.  If not, see <http://www.gnu.org/licenses/>       *
*                                                                     *
* Contact: Cristian.Lalescu@ds.mpg.de                                 *
*                                                                     *
**********************************************************************/



#include <mpi.h>
#include <hdf5.h>
#include <fftw3-mpi.h>
#include <vector>

#ifndef FIELD

#define FIELD

enum field_representation {REAL, COMPLEX, BOTH};
enum field_backend {FFTW};
enum field_components {ONE, THREE, THREExTHREE};

constexpr unsigned int ncomp(
        field_components fc)
    /* return actual number of field components for each enum value */
{
    return ((fc == THREE) ? 3 : (
            (fc == THREExTHREE) ? 9 : 1));
}

constexpr unsigned int ndim(
        field_components fc)
    /* return actual number of field dimensions for each enum value */
{
    return ((fc == THREE) ? 4 : (
            (fc == THREExTHREE) ? 5 : 3));
}

template <class number,
          field_backend be,
          field_components fc>
class field_container
{
    public:
        /* description */
        hsize_t sizes[ndim(fc)];
        hsize_t subsizes[ndim(fc)];
        hsize_t starts[ndim(fc)];
        ptrdiff_t slice_size, local_size, full_size;

        int myrank, nprocs;
        MPI_Comm comm;

        std::vector<int> rank;
        std::vector<std::vector<int>> all_start;
        std::vector<std::vector<int>> all_size;

        number *data;

        /* methods */
        field_container(
                int nx, int ny, int nz,
                MPI_Comm COMM_TO_USE);
        ~field_container();

        int read(
                const char *fname,
                const char *dset_name,
                int iteration);

        int write(
                const char *fname,
                const char *dset_name,
                int iteration);
};

//template <class rnum,
//          field_representation repr,
//          field_backend be,
//          field_components fc>
//class field
//{
//    public:
//
//        field_container< *kdata, *rdata;
//
//        /* methods */
//        field(
//                int *n,
//                MPI_Comm COMM_TO_USE);
//        ~field();
//};

#endif//FIELD


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



#include "field_descriptor.hpp"
#include "fftw_tools.hpp"
#include "fluid_solver_base.hpp"
#include "spline_n1.hpp"
#include "spline_n2.hpp"
#include "spline_n3.hpp"
#include "spline_n4.hpp"
#include "spline_n5.hpp"
#include "spline_n6.hpp"
#include "Lagrange_polys.hpp"
#include "interpolator.hpp"

#ifndef RFFTW_INTERPOLATOR

#define RFFTW_INTERPOLATOR

template <class rnumber, int interp_neighbours>
class rFFTW_interpolator
{
    public:
        /* size of field to interpolate */
        ptrdiff_t field_size;

        /* pointer to polynomial function */
        base_polynomial_values compute_beta;

        /* descriptor of field to interpolate */
        field_descriptor<rnumber> *descriptor;

        /* pointers to fields that are to be interpolated
         * */
        rnumber *f0, *f1, *temp;

        /* physical parameters of field */
        double dx, dy, dz;

        /* precomputed boundaries of process's domain */
        double *lbound;
        double *ubound;

        rFFTW_interpolator(
                fluid_solver_base<rnumber> *FSOLVER,
                base_polynomial_values BETA_POLYS);
        ~rFFTW_interpolator();

        /* map real locations to grid coordinates */
        void get_grid_coordinates(
                const int nparticles,
                const int pdimension,
                const double *__restrict__ x,
                int *__restrict__ xg,
                double *__restrict__ xx);
        /* interpolate field at an array of locations */
        void sample(
                const int nparticles,
                const double t,
                const double *__restrict__ x,
                double *__restrict__ y,
                const int *deriv = NULL);
        /* interpolate 1 point */
        void operator()(
                const double t,
                const int *__restrict__ xg,
                const double *__restrict__ xx,
                double *__restrict__ dest,
                const int *deriv = NULL);
        int read_rFFTW(void *src);
};

#endif//RFFTW_INTERPOLATOR


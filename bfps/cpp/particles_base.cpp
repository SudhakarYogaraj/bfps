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



#define NDEBUG

#include <algorithm>
#include <cassert>
#include "particles_base.hpp"
#include "scope_timer.hpp"

template <particle_types particle_type>
single_particle_state<particle_type>::single_particle_state()
{
    std::fill_n(this->data, state_dimension(particle_type), 0);
}

template <particle_types particle_type>
single_particle_state<particle_type>::single_particle_state(
        const single_particle_state<particle_type> &src)
{
    std::copy(
            src.data,
            src.data + state_dimension(particle_type),
            this->data);
}

template <particle_types particle_type>
single_particle_state<particle_type>::single_particle_state(
        const double *src)
{
    std::copy(
            src,
            src + state_dimension(particle_type),
            this->data);
}

template <particle_types particle_type>
single_particle_state<particle_type>::~single_particle_state()
{
}

template <particle_types particle_type>
single_particle_state<particle_type> &single_particle_state<particle_type>::operator=(
        const single_particle_state &src)
{
    std::copy(
            src.data,
            src.data + state_dimension(particle_type),
            this->data);
    return *this;
}

template <particle_types particle_type>
single_particle_state<particle_type> &single_particle_state<particle_type>::operator=(
        const double *src)
{
    std::copy(
            src,
            src + state_dimension(particle_type),
            this->data);
    return *this;
}

int get_chunk_offsets(
        std::vector<hsize_t> data_dims,
        std::vector<hsize_t> chnk_dims,
        std::vector<std::vector<hsize_t>> &co)
{
    TIMEZONE("get_chunk_offsets");
    std::vector<hsize_t> nchunks(data_dims);
    int total_number_of_chunks = 1;
    for (unsigned i=0; i<nchunks.size(); i++)
    {
        DEBUG_MSG("get_chunk_offset nchunks[%d] = %ld, chnk_dims[%d] = %ld\n",
                i, nchunks[i], i, chnk_dims[i]);
        nchunks[i] = data_dims[i] / chnk_dims[i];
        total_number_of_chunks *= nchunks[i];
    }
    co.resize(total_number_of_chunks);
    DEBUG_MSG("total number of chunks is %d\n", total_number_of_chunks);
    for (int cindex=0; cindex < total_number_of_chunks; cindex++)
    {
        int cc = cindex;
        for (unsigned i=0; i<nchunks.size(); i++)
        {
            int ii = nchunks.size()-1-i;
            co[cindex].resize(nchunks.size());
            co[cindex][ii] = cc % nchunks[ii];
            cc = (cc - co[cindex][ii]) / nchunks[ii];
            co[cindex][ii] *= chnk_dims[ii];
        }
    }
    return EXIT_SUCCESS;
}

template <particle_types particle_type>
particles_io_base<particle_type>::particles_io_base(
        const char *NAME,
        const int TRAJ_SKIP,
        const hid_t data_file_id,
        MPI_Comm COMM)
{
    TIMEZONE("particles_io_base::particles_io_base");
    this->name = std::string(NAME);
    this->traj_skip = TRAJ_SKIP;
    this->comm = COMM;
    MPI_Comm_rank(COMM, &this->myrank);
    MPI_Comm_size(COMM, &this->nprocs);

    if (this->myrank == 0)
    {
        hid_t dset, prop_list, dspace;
        this->hdf5_group_id = H5Gopen(data_file_id, this->name.c_str(), H5P_DEFAULT);
        dset = H5Dopen(this->hdf5_group_id, "state", H5P_DEFAULT);
        dspace = H5Dget_space(dset);
        this->hdf5_state_dims.resize(H5Sget_simple_extent_ndims(dspace));
        H5Sget_simple_extent_dims(dspace, &this->hdf5_state_dims.front(), NULL);
        assert(this->hdf5_state_dims[this->hdf5_state_dims.size()-1] == state_dimension(particle_type));
        this->nparticles = 1;
        for (unsigned int i=1; i<this->hdf5_state_dims.size()-1; i++)
            this->nparticles *= this->hdf5_state_dims[i];
        prop_list = H5Dget_create_plist(dset);
        this->hdf5_state_chunks.resize(this->hdf5_state_dims.size());
        H5Pget_chunk(prop_list, this->hdf5_state_dims.size(), &this->hdf5_state_chunks.front());
        H5Pclose(prop_list);
        H5Sclose(dspace);
        H5Dclose(dset);
        this->chunk_size = 1;
        for (unsigned int i=1; i<this->hdf5_state_dims.size()-1; i++)
            this->chunk_size *= this->hdf5_state_chunks[i];
        dset = H5Dopen(this->hdf5_group_id, "rhs", H5P_DEFAULT);
        dspace = H5Dget_space(dset);
        this->hdf5_rhs_dims.resize(H5Sget_simple_extent_ndims(dspace));
        H5Sget_simple_extent_dims(dspace, &this->hdf5_rhs_dims.front(), NULL);
        prop_list = H5Dget_create_plist(dset);
        this->hdf5_rhs_chunks.resize(this->hdf5_rhs_dims.size());
        H5Pget_chunk(prop_list, this->hdf5_rhs_dims.size(), &this->hdf5_rhs_chunks.front());
        H5Pclose(prop_list);
        H5Sclose(dspace);
        H5Dclose(dset);
    }
    DEBUG_MSG("hello, rank 0 just read particle thingie\n");

    int tmp;
    tmp = this->hdf5_state_dims.size();
    MPI_Bcast(
            &tmp,
            1,
            MPI_INTEGER,
            0,
            this->comm);
    if (this->myrank != 0)
    {
        this->hdf5_state_dims.resize(tmp);
        this->hdf5_state_chunks.resize(tmp);
    }
    DEBUG_MSG("successfully resized state_dims and state_chunks\n");
    MPI_Bcast(
            &this->hdf5_state_dims.front(),
            this->hdf5_state_dims.size(),
            // hsize_t is in fact unsigned long long. Will this ever change...?
            MPI_UNSIGNED_LONG_LONG,
            0,
            this->comm);
    MPI_Bcast(
            &this->hdf5_state_chunks.front(),
            this->hdf5_state_chunks.size(),
            MPI_UNSIGNED_LONG_LONG,
            0,
            this->comm);
    DEBUG_MSG("successfully broadcasted state_dims and state_chunks\n");
    for (unsigned i=0; i<this->hdf5_state_chunks.size(); i++)
        DEBUG_MSG(
                "hdf5_state_dims[%d] = %ld, hdf5_state_chunks[%d] = %ld\n",
                i, this->hdf5_state_dims[i],
                i, this->hdf5_state_chunks[i]
                );
    std::vector<hsize_t> tdims(this->hdf5_state_dims), tchnk(this->hdf5_state_chunks);
    tdims.erase(tdims.begin()+0);
    tchnk.erase(tchnk.begin()+0);
    tdims.erase(tdims.end()-1);
    tchnk.erase(tchnk.end()-1);
    DEBUG_MSG("before get_chunk_offsets\n");
    get_chunk_offsets(tdims, tchnk, this->chunk_offsets);
    DEBUG_MSG("after get_chunk_offsets\n");
    MPI_Bcast(
            &this->chunk_size,
            1,
            MPI_UNSIGNED,
            0,
            this->comm);
    MPI_Bcast(
            &this->nparticles,
            1,
            MPI_UNSIGNED,
            0,
            this->comm);
    DEBUG_MSG("nparticles = %d, chunk_size = %d\n",
            this->nparticles,
            this->chunk_size);
    DEBUG_MSG("exiting particles_io_base constructor\n");
}

template <particle_types particle_type>
particles_io_base<particle_type>::~particles_io_base()
{
    if(this->myrank == 0)
        H5Gclose(this->hdf5_group_id);
}

template <particle_types particle_type>
void particles_io_base<particle_type>::read_state_chunk(
        const int cindex,
        double *data)
{
    TIMEZONE("particles_io_base::read_state_chunk");
    DEBUG_MSG("entered read_state_chunk\n");
    hid_t dset = H5Dopen(this->hdf5_group_id, "state", H5P_DEFAULT);
    hid_t rspace = H5Dget_space(dset);
    std::vector<hsize_t> mem_dims(this->hdf5_state_chunks);
    mem_dims[0] = 1;
    hid_t mspace = H5Screate_simple(
            this->hdf5_state_dims.size(),
            &mem_dims.front(),
            NULL);
    hsize_t *offset = new hsize_t[this->hdf5_state_dims.size()];
    offset[0] = this->iteration / this->traj_skip;
    for (unsigned int i=1; i<this->hdf5_state_dims.size()-1; i++)
        offset[i] = this->chunk_offsets[cindex][i-1];
    offset[this->hdf5_state_dims.size()-1] = 0;
    H5Sselect_hyperslab(
            rspace,
            H5S_SELECT_SET,
            offset,
            NULL,
            &mem_dims.front(),
            NULL);
    H5Dread(dset, H5T_NATIVE_DOUBLE, mspace, rspace, H5P_DEFAULT, data);
    H5Sclose(mspace);
    H5Sclose(rspace);
    H5Dclose(dset);
    delete[] offset;
    DEBUG_MSG("exiting read_state_chunk\n");
}

template <particle_types particle_type>
void particles_io_base<particle_type>::write_state_chunk(
        const int cindex,
        const double *data)
{
    TIMEZONE("particles_io_base::write_state_chunk");
    hid_t dset = H5Dopen(this->hdf5_group_id, "state", H5P_DEFAULT);
    hid_t rspace = H5Dget_space(dset);
    std::vector<hsize_t> mem_dims(this->hdf5_state_chunks);
    mem_dims[0] = 1;
    hid_t mspace = H5Screate_simple(
            this->hdf5_state_dims.size(),
            &mem_dims.front(),
            NULL);
    hsize_t *offset = new hsize_t[this->hdf5_state_dims.size()];
    offset[0] = this->iteration / this->traj_skip;
    for (unsigned int i=1; i<this->hdf5_state_dims.size()-1; i++)
        offset[i] = this->chunk_offsets[cindex][i-1];
    offset[this->hdf5_state_dims.size()-1] = 0;
    H5Sselect_hyperslab(
            rspace,
            H5S_SELECT_SET,
            offset,
            NULL,
            &mem_dims.front(),
            NULL);
    H5Dwrite(dset, H5T_NATIVE_DOUBLE, mspace, rspace, H5P_DEFAULT, data);
    H5Sclose(mspace);
    H5Sclose(rspace);
    H5Dclose(dset);
    delete[] offset;
}

template <particle_types particle_type>
void particles_io_base<particle_type>::read_rhs_chunk(
        const int cindex,
        const int rhsindex,
        double *data)
{
    TIMEZONE("particles_io_base::read_rhs_chunk");
    //DEBUG_MSG("entered read_rhs_chunk\n");
    hid_t dset = H5Dopen(this->hdf5_group_id, "rhs", H5P_DEFAULT);
    hid_t rspace = H5Dget_space(dset);
    std::vector<hsize_t> mem_dims(this->hdf5_rhs_chunks);
    mem_dims[0] = 1;
    mem_dims[1] = 1;
    hid_t mspace = H5Screate_simple(
            this->hdf5_rhs_dims.size(),
            &mem_dims.front(),
            NULL);
    hsize_t *offset = new hsize_t[this->hdf5_rhs_dims.size()];
    offset[0] = this->hdf5_rhs_dims[0]-2;
    offset[1] = rhsindex;
    for (unsigned int i=2; i<this->hdf5_rhs_dims.size()-1; i++)
        offset[i] = this->chunk_offsets[cindex][i-2];
    offset[this->hdf5_rhs_dims.size()-1] = 0;
    //for (int i=0; i<this->hdf5_rhs_dims.size(); i++)
    //    DEBUG_MSG("rhs dim %d: size=%d chunk=%d offset=%d\n",
    //        i, this->hdf5_rhs_dims[i], this->hdf5_rhs_chunks[i], offset[i]);
    H5Sselect_hyperslab(
            rspace,
            H5S_SELECT_SET,
            offset,
            NULL,
            &mem_dims.front(),
            NULL);
    //DEBUG_MSG("selected hyperslab\n");
    H5Dread(dset, H5T_NATIVE_DOUBLE, mspace, rspace, H5P_DEFAULT, data);
    //DEBUG_MSG("data has been read\n");
    H5Sclose(mspace);
    H5Sclose(rspace);
    H5Dclose(dset);
    delete[] offset;
    //DEBUG_MSG("exiting read_rhs_chunk\n");
}

template <particle_types particle_type>
void particles_io_base<particle_type>::write_rhs_chunk(
        const int cindex,
        const int rhsindex,
        const double *data)
{
    TIMEZONE("particles_io_base::write_rhs_chunk");
    hid_t dset = H5Dopen(this->hdf5_group_id, "rhs", H5P_DEFAULT);
    hid_t rspace = H5Dget_space(dset);
    std::vector<hsize_t> mem_dims(this->hdf5_rhs_chunks);
    mem_dims[0] = 1;
    mem_dims[1] = 1;
    hid_t mspace = H5Screate_simple(
            this->hdf5_rhs_dims.size(),
            &mem_dims.front(),
            NULL);
    hsize_t *offset = new hsize_t[this->hdf5_rhs_dims.size()];
    offset[0] = this->hdf5_rhs_dims[0]-1;
    offset[1] = rhsindex;
    for (unsigned int i=2; i<this->hdf5_rhs_dims.size()-1; i++)
        offset[i] = this->chunk_offsets[cindex][i-2];
    offset[this->hdf5_rhs_dims.size()-1] = 0;
    DEBUG_MSG("rhs write offsets are %d %d %d %d\n",
            offset[0], offset[1], offset[2], offset[3]);
    H5Sselect_hyperslab(
            rspace,
            H5S_SELECT_SET,
            offset,
            NULL,
            &mem_dims.front(),
            NULL);
    H5Dwrite(dset, H5T_NATIVE_DOUBLE, mspace, rspace, H5P_DEFAULT, data);
    H5Sclose(mspace);
    H5Sclose(rspace);
    H5Dclose(dset);
    delete[] offset;
}

template <particle_types particle_type>
void particles_io_base<particle_type>::write_point3D_chunk(
        const std::string dset_name,
        const int cindex,
        const double *data)
{
    TIMEZONE("particles_io_base::write_point3D_chunk");
    hid_t dset = H5Dopen(this->hdf5_group_id, dset_name.c_str(), H5P_DEFAULT);
    hid_t rspace = H5Dget_space(dset);
    std::vector<hsize_t> mem_dims(this->hdf5_state_chunks);
    mem_dims[0] = 1;
    mem_dims[mem_dims.size()-1] = 3;
    hid_t mspace = H5Screate_simple(
            this->hdf5_state_dims.size(),
            &mem_dims.front(),
            NULL);
    hsize_t *offset = new hsize_t[this->hdf5_state_dims.size()];
    offset[0] = this->iteration / this->traj_skip;
    for (unsigned int i=1; i<this->hdf5_state_dims.size()-1; i++)
        offset[i] = this->chunk_offsets[cindex][i-1];
    offset[this->hdf5_state_dims.size()-1] = 0;
    H5Sselect_hyperslab(
            rspace,
            H5S_SELECT_SET,
            offset,
            NULL,
            &mem_dims.front(),
            NULL);
    H5Dwrite(dset, H5T_NATIVE_DOUBLE, mspace, rspace, H5P_DEFAULT, data);
    H5Sclose(mspace);
    H5Sclose(rspace);
    H5Dclose(dset);
    delete[] offset;
}

/*****************************************************************************/
template class single_particle_state<POINT3D>;
template class single_particle_state<VELOCITY_TRACER>;

template class particles_io_base<VELOCITY_TRACER>;
/*****************************************************************************/


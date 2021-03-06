#ifndef PARTICLES_FIELD_COMPUTER_HPP
#define PARTICLES_FIELD_COMPUTER_HPP

#include <array>
#include <utility>

#include "scope_timer.hpp"
#include "particles_utils.hpp"

template <class partsize_t,
          class real_number,
          class interpolator_class,
          int interp_neighbours>
class particles_field_computer {

    const std::array<int,3> field_grid_dim;
    const std::pair<int,int> current_partition_interval;

    const interpolator_class& interpolator;

    const std::array<real_number,3> spatial_box_width;
    const std::array<real_number,3> spatial_box_offset;
    const std::array<real_number,3> box_step_width;

    int deriv[3];

public:

    particles_field_computer(const std::array<size_t,3>& in_field_grid_dim,
                             const std::pair<int,int>& in_current_partitions,
                             const interpolator_class& in_interpolator,
                             const std::array<real_number,3>& in_spatial_box_width, const std::array<real_number,3>& in_spatial_box_offset,
                             const std::array<real_number,3>& in_box_step_width)
        : field_grid_dim({{int(in_field_grid_dim[0]),int(in_field_grid_dim[1]),int(in_field_grid_dim[2])}}), current_partition_interval(in_current_partitions),
          interpolator(in_interpolator),
          spatial_box_width(in_spatial_box_width), spatial_box_offset(in_spatial_box_offset), box_step_width(in_box_step_width){
        deriv[IDX_X] = 0;
        deriv[IDX_Y] = 0;
        deriv[IDX_Z] = 0;
    }

    ////////////////////////////////////////////////////////////////////////
    /// Computation related
    ////////////////////////////////////////////////////////////////////////

    template <int size_particle_rhs>
    void init_result_array(real_number particles_current_rhs[],
                                   const partsize_t nb_particles) const {
        // Set values to zero initialy
        std::fill(particles_current_rhs,
                  particles_current_rhs+nb_particles*size_particle_rhs,
                  0);
    }

    real_number get_norm_pos_in_cell(const real_number in_pos, const int idx_pos) const {
        const real_number shifted_pos = in_pos - spatial_box_offset[idx_pos];
        const real_number nb_box_repeat = floor(shifted_pos/spatial_box_width[idx_pos]);
        const real_number pos_in_box = shifted_pos - nb_box_repeat*spatial_box_width[idx_pos];
        const real_number cell_idx = floor(pos_in_box/box_step_width[idx_pos]);
        const real_number pos_in_cell = (pos_in_box - cell_idx*box_step_width[idx_pos]) / box_step_width[idx_pos];
        assert(0 <= pos_in_cell && pos_in_cell < 1);
        return pos_in_cell;
    }

    template <class field_class, int size_particle_rhs>
    void apply_computation(const field_class& field,
                                   const real_number particles_positions[],
                                   real_number particles_current_rhs[],
                                   const partsize_t nb_particles) const {
        TIMEZONE("particles_field_computer::apply_computation");
        //DEBUG_MSG("just entered particles_field_computer::apply_computation\n");
        for(partsize_t idxPart = 0 ; idxPart < nb_particles ; ++idxPart){
            const real_number reltv_x = get_norm_pos_in_cell(particles_positions[idxPart*3+IDX_X], IDX_X);
            const real_number reltv_y = get_norm_pos_in_cell(particles_positions[idxPart*3+IDX_Y], IDX_Y);
            const real_number reltv_z = get_norm_pos_in_cell(particles_positions[idxPart*3+IDX_Z], IDX_Z);

            typename interpolator_class::real_number
                bx[interp_neighbours*2+2],
                by[interp_neighbours*2+2],
                bz[interp_neighbours*2+2];
            interpolator.compute_beta(deriv[IDX_X], reltv_x, bx);
            interpolator.compute_beta(deriv[IDX_Y], reltv_y, by);
            interpolator.compute_beta(deriv[IDX_Z], reltv_z, bz);

            const int partGridIdx_x = pbc_field_layer(particles_positions[idxPart*3+IDX_X], IDX_X);
            const int partGridIdx_y = pbc_field_layer(particles_positions[idxPart*3+IDX_Y], IDX_Y);
            const int partGridIdx_z = pbc_field_layer(particles_positions[idxPart*3+IDX_Z], IDX_Z);

            assert(0 <= partGridIdx_x && partGridIdx_x < int(field_grid_dim[IDX_X]));
            assert(0 <= partGridIdx_y && partGridIdx_y < int(field_grid_dim[IDX_Y]));
            assert(0 <= partGridIdx_z && partGridIdx_z < int(field_grid_dim[IDX_Z]));

            const int interp_limit_mx = partGridIdx_x-interp_neighbours;
            const int interp_limit_x = partGridIdx_x+interp_neighbours+1;
            const int interp_limit_my = partGridIdx_y-interp_neighbours;
            const int interp_limit_y = partGridIdx_y+interp_neighbours+1;
            const int interp_limit_mz_bz = partGridIdx_z-interp_neighbours;

            int interp_limit_mz[2];
            int interp_limit_z[2];
            int nb_z_intervals;

            if((partGridIdx_z-interp_neighbours) < 0){
                assert(partGridIdx_z+interp_neighbours+1 < int(field_grid_dim[IDX_Z]));
                interp_limit_mz[0] = std::max(current_partition_interval.first, partGridIdx_z-interp_neighbours+int(field_grid_dim[IDX_Z]));
                interp_limit_z[0] = current_partition_interval.second-1;

                interp_limit_mz[1] = std::max(0, current_partition_interval.first);
                interp_limit_z[1] = std::min(partGridIdx_z+interp_neighbours+1, current_partition_interval.second-1);

                nb_z_intervals = 2;
            }
            else if(int(field_grid_dim[IDX_Z]) <= (partGridIdx_z+interp_neighbours+1)){
                interp_limit_mz[0] = std::max(current_partition_interval.first, partGridIdx_z-interp_neighbours);
                interp_limit_z[0] = std::min(int(field_grid_dim[IDX_Z])-1,current_partition_interval.second-1);

                interp_limit_mz[1] = std::max(0, current_partition_interval.first);
                interp_limit_z[1] = std::min(partGridIdx_z+interp_neighbours+1-int(field_grid_dim[IDX_Z]), current_partition_interval.second-1);

                nb_z_intervals = 2;
            }
            else{
                interp_limit_mz[0] = std::max(partGridIdx_z-interp_neighbours, current_partition_interval.first);
                interp_limit_z[0] = std::min(partGridIdx_z+interp_neighbours+1, current_partition_interval.second-1);
                nb_z_intervals = 1;
            }

            for(int idx_inter = 0 ; idx_inter < nb_z_intervals ; ++idx_inter){
                for(int idx_z = interp_limit_mz[idx_inter] ; idx_z <= interp_limit_z[idx_inter] ; ++idx_z ){
                    const int idx_z_pbc = (idx_z + field_grid_dim[IDX_Z])%field_grid_dim[IDX_Z];
                    assert(current_partition_interval.first <= idx_z_pbc && idx_z_pbc < current_partition_interval.second);
                    assert(((idx_z+field_grid_dim[IDX_Z]-interp_limit_mz_bz)%field_grid_dim[IDX_Z]) < interp_neighbours*2+2);

                    for(int idx_x = interp_limit_mx ; idx_x <= interp_limit_x ; ++idx_x ){
                        const int idx_x_pbc = (idx_x + field_grid_dim[IDX_X])%field_grid_dim[IDX_X];
                        assert(idx_x-interp_limit_mx < interp_neighbours*2+2);

                        for(int idx_y = interp_limit_my ; idx_y <= interp_limit_y ; ++idx_y ){
                            const int idx_y_pbc = (idx_y + field_grid_dim[IDX_Y])%field_grid_dim[IDX_Y];
                            assert(idx_y-interp_limit_my < interp_neighbours*2+2);

                            const real_number coef = (bz[((idx_z+field_grid_dim[IDX_Z]-interp_limit_mz_bz)%field_grid_dim[IDX_Z])]
                                                    * by[idx_y-interp_limit_my]
                                                    * bx[idx_x-interp_limit_mx]);

                            const ptrdiff_t tindex = field.get_rindex_from_global(idx_x_pbc, idx_y_pbc, idx_z_pbc);

                            // getValue does not necessary return real_number
                            for(int idx_rhs_val = 0 ; idx_rhs_val < size_particle_rhs ; ++idx_rhs_val){
                                particles_current_rhs[idxPart*size_particle_rhs+idx_rhs_val] += real_number(field.rval(tindex,idx_rhs_val))*coef;
                            }
                        }
                    }
                }
            }
        }
    }

    template <int size_particle_rhs>
    void reduce_particles_rhs(real_number particles_current_rhs[],
                                  const real_number extra_particles_current_rhs[],
                                  const partsize_t nb_particles) const {
        TIMEZONE("particles_field_computer::reduce_particles");
        // Simply sum values
        for(partsize_t idxPart = 0 ; idxPart < nb_particles ; ++idxPart){
            for(int idx_rhs_val = 0 ; idx_rhs_val < size_particle_rhs ; ++idx_rhs_val){
                particles_current_rhs[idxPart*size_particle_rhs+idx_rhs_val] += extra_particles_current_rhs[idxPart*size_particle_rhs+idx_rhs_val];
            }
        }
    }

    ////////////////////////////////////////////////////////////////////////
    /// Re-distribution related
    ////////////////////////////////////////////////////////////////////////

    int pbc_field_layer(const real_number& a_z_pos, const int idx_dim) const {
        const real_number shifted_pos = a_z_pos - spatial_box_offset[idx_dim];
        const int nb_level_to_pos = int(floor(shifted_pos/box_step_width[idx_dim]));
        const int int_field_grid_dim = int(field_grid_dim[idx_dim]);
        const int pbc_level = ((nb_level_to_pos%int_field_grid_dim)+int_field_grid_dim)%int_field_grid_dim;
        assert(0 <= pbc_level && pbc_level < int(field_grid_dim[idx_dim]));
        return pbc_level;
    }

};


#endif

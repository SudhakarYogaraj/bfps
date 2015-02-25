########################################################################
#
#  Copyright 2015 Johns Hopkins University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contact: turbulence@pha.jhu.edu
# Website: http://turbulence.pha.jhu.edu/
#
########################################################################



MPICXX  = mpicxx
LINKER  = mpicxx
DEFINES = -DNDEBUG
CFLAGS  = -Wall \
		  -O2 \
		  #-pg \
		  #-finstrument-functions

LIBS = -lfftw3_mpi \
	   -lfftw3 \
	   -lfftw3f_mpi \
	   -lfftw3f

COMPILER_VERSION := $(shell ${MPICXX} --version)

ifneq (,$(findstring ICC,$(COMPILER_VERSION)))
	# using intel compiler
	# advice from
	# https://software.intel.com/en-us/forums/topic/298872
	# always link against both libimf and libm
    LIBS += -limf \
			-lm
else
    # not using intel compiler
endif

base_files := \
	field_descriptor \
	fftwf_tools \
	Morton_shuffler \
	p3DFFT_to_iR

#headers := $(patsubst %, ./src/%.hpp, ${base_files})
src := $(patsubst %, ./src/%.cpp, ${base_files})
obj := $(patsubst %, ./obj/%.o, ${base_files})

.PRECIOUS: ./obj/%.o

./obj/%.o: ./src/%.cpp
	${MPICXX} ${DEFINES} \
		${CFLAGS} \
		-c $^ -o $@

base: ${obj}

%.elf: ${obj} ./obj/%.o
	${LINKER} \
		$^ \
		-o $@ \
		${LIBS} \
		${NULL}

clean:
	rm -f ./obj/*.o
	rm -f *.elf


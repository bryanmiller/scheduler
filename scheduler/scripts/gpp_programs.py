#!/usr/bin/env python3
# Copyright (c) 2016-2024 Association of Universities for Research in Astronomy, Inc. (AURA)
# For license information see LICENSE or https://opensource.org/licenses/BSD-3-Clause

import os, sys

# Requires https://github.com/andrewwstephens/pyexplore
# sys.path.append(os.path.join(os.environ['PYEXPLORE']))
# Uncomment the next three lines to run from the pycharm terminal, better to redefine PYTHONPATH in the terminal
# sys.path.append(os.path.join(os.environ['HOME'], 'python', 'pyexplore'))
# sys.path.append(os.path.join(os.environ['HOME'], 'python', 'scheduler'))
# sys.path.append(os.path.join(os.environ['HOME'], 'python', 'lucupy'))
# from pyexplore import __version__
from pyexplore.pyexplore import explore, schema

from scheduler.core.programprovider.gpp.gppprogramprovider import GppProgramProvider
from scheduler.core.sources.sources import Sources
from lucupy.minimodel.observation import ObservationClass

if __name__ == '__main__':

    sources = Sources()
    provider = GppProgramProvider(frozenset([ObservationClass.SCIENCE]), sources)

    # List programs
    # TODO change pyexplore to other api query
    programs = explore.get_programs(include_deleted=False)
    # programs = []
    progid = None
    for p in programs:
        print(f'{p["id"]}: {p["name"]}')
        # progid = p["id"] if progid is None else progid
    print("")

    progid = 'p-913'

    # TODO change pyexplore to other api query
    prog = explore.get_program(progid)
    # prog = {}
    print(f'{progid} {prog.reference.label}: {prog.name}')

    # Parse into minimodel
    prog_mini = provider.parse_program(prog.__dict__)

    prog_mini.show()
    print("")
    print(prog_mini.root_group.number_to_observe, prog_mini.root_group.group_option)
    print(prog_mini.semester, prog_mini.type, prog_mini.mode)
    print(prog_mini.start, prog_mini.end)
    # print(prog_mini.allocated_time)
    print(prog_mini.program_awarded(), prog_mini.partner_awarded(), prog_mini.total_awarded())
    print(prog_mini.used_time)
    print(prog_mini.bands())
    for alloc in prog_mini.allocated_time:
        print(alloc.category.name, alloc.program_awarded, alloc.band.name)



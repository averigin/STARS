%
% Copyright (C) 2011 Eamon Millman
%
% This program is free software; you can redistribute it and/or
% modify it under the terms of the GNU Lesser General Public License
% as published by the Free Software Foundation; either version 2
% of the License, or (at your option) any later version.
%
% This program is distributed in the hope that it will be useful,
% but WITHOUT ANY WARRANTY; without even the implied warranty of
% MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
% GNU Lesser General Public License for more details.
%
% You should have received a copy of the GNU Lesser General Public License
% along with this program; if not, see <http://www.gnu.org/licenses/>.
%

% this script submits a serial (single process) job to the matlab scheduler
% on westgrid

function [] = submitSerialJob( clusterHost, email, remoteDataLocation, remoteMatlabLocation, ram, walltime, procs, dev, script, funcName )

    % appends the .m suffix to the configuration script specified.
    scriptFile = sprintf('%s.m', script );

    % obtain the scheduler object for a serial job
    sched = getPbs( clusterHost, email, remoteDataLocation, ram, walltime, procs, dev );

    % create the job
    j = createJob(sched);

    % attach matlab_wg.m bootstrap script to the submission
    j.FileDependencies={scriptFile,'matlab_wg.m'};

    % create the matlab distributed computing task
    t = createTask(j,@matlab_wg, 1, {funcName, script, remoteMatlabLocation } );
    % put all command window output into a variable commandwindowoutput
    % contained in remoteDataLocation/Job#/Task1.out.mat
    set(t, 'CaptureCommandWindowOutput', true);

    % send job to westgrid to be scheduled for processing.
    submit(j);

end
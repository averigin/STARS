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

% this function provides the specified feature's time-series data
function [ ts_data ] = timeseriesReverse( ts_data )

	[ times, idx ] = sort( ts_data.times, 'descend' );
    clear times;
    ts_data.times = ts_data.times(idx);
    ts_data.values = ts_data.values(idx);
    
end
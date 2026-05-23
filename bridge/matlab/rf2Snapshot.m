function data = rf2Snapshot(varargin)
%RF2SNAPSHOT Read one rFactor 2 telemetry snapshot.
client = RF2Client();
data = client.snapshot(varargin{:});
end

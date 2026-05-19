function data = rf2Status()
%RF2STATUS Report rFactor 2 shared-memory connection status.
client = RF2Client();
data = client.status();
disp(data);
end

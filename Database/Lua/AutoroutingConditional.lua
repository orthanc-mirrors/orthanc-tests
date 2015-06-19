function OnStoredInstance(instanceId, tags, metadata, remoteAet, calledAet)
   -- The "remoteAet" and "calledAet" arguments are only available
   -- since Orthanc 0.8.6
   if remoteAet ~=nil and calledAet ~= nil then
      print ("Source AET: " .. remoteAet .. " => Called AET: " .. calledAet)
   end

   -- Extract the value of the "PatientName" DICOM tag
   local patientName = string.lower(tags['PatientName'])

   if string.find(patientName, 'knee') ~= nil then
      -- Only send patients whose name contains "Knee"
      Delete(SendToModality(instanceId, 'orthanctest'))

   else
      -- Delete the patients that are not called "Knee"
      Delete(instanceId)
   end
end

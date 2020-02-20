-- for these tests, we issue HTTP requests to httpbin.org that performs smart echo (it returns all data/headers it has received + some extra data)

testSucceeded = true

local payload = {}
payload['stringMember'] = 'toto'
payload['intMember'] = 2

local httpHeaders = {}
httpHeaders['Content-Type'] = 'application/json'
httpHeaders['Toto'] = 'Tutu'

-- Issue HttpPost with body
response = ParseJson(HttpPost('http://httpbin.org/post', DumpJson(payload), httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')
testSucceeded = testSucceeded and (response['json']['intMember'] == 2 and response['json']['stringMember'] == 'toto')
if not testSucceeded then print('Failed in HttpPost with body') PrintRecursive(response) end

-- Issue HttpPost without body
response = ParseJson(HttpPost('http://httpbin.org/post', nil, httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')
testSucceeded = testSucceeded and (response['data'] == '')
if not testSucceeded then print('Failed in HttpPost without body') PrintRecursive(response) end

-- Issue HttpPut with body
response = ParseJson(HttpPut('http://httpbin.org/put', DumpJson(payload), httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')
testSucceeded = testSucceeded and (response['json']['intMember'] == 2 and response['json']['stringMember'] == 'toto')
if not testSucceeded then print('Failed in HttpPut with body') PrintRecursive(response) end

-- Issue HttpPut without body
response = ParseJson(HttpPut('http://httpbin.org/put', nil, httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')
testSucceeded = testSucceeded and (response['data'] == '')
if not testSucceeded then print('Failed in HttpPut without body') PrintRecursive(response) end

-- Issue HttpDelete (juste make sure it is issued, we can't check the response)
HttpDelete('http://httpbin.org/delete', httpHeaders)

-- TODO Very strange: Since Orthanc 1.6.0, a timeout frequently occurs
-- in curl at this point

-- Issue HttpGet
response = ParseJson(HttpGet('http://httpbin.org/get', httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')
if not testSucceeded then print('Failed in HttpGet') PrintRecursive(response) end

if testSucceeded then
	print('OK')
else
	print('FAILED')
end

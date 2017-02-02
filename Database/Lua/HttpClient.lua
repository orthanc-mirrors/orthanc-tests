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

-- Issue HttpPost without body
response = ParseJson(HttpPost('http://httpbin.org/post', nil, httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')
testSucceeded = testSucceeded and (response['json']['intMember'] == 2 and response['json']['stringMember'] == 'toto')
PrintRecursive(response)

-- Issue HttpPut with body
response = ParseJson(HttpPut('http://httpbin.org/put', DumpJson(payload), httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')

-- Issue HttpPut without body
response = ParseJson(HttpPut('http://httpbin.org/put', nil, httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')

-- Issue HttpDelete (juste make sure it is issued, we can't check the response)
HttpDelete('http://httpbin.org/delete', httpHeaders)

-- Issue HttpGet
response = ParseJson(HttpGet('http://httpbin.org/get', httpHeaders))
testSucceeded = testSucceeded and (response['headers']['Content-Type'] == 'application/json' and response['headers']['Toto'] == 'Tutu')

if testSucceeded then
	print('OK')
else
	print('FAILED')
end

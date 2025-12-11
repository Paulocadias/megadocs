# Code Examples

## Python

### Basic Conversion
```python
import requests

url = "https://megadocs.paulocadias.com/api/convert"
files = {'file': open('document.pdf', 'rb')}

response = requests.post(url, files=files)
data = response.json()

if data['success']:
    print(data['content'])
    # Save to file
    with open('output.md', 'w', encoding='utf-8') as f:
        f.write(data['content'])
```

### Convert to Plain Text
```python
files = {'file': open('document.pdf', 'rb')}
data = {'output_format': 'text'}

response = requests.post(url, files=files, data=data)
result = response.json()

if result['success']:
    print(result['content'])
```

### With API Key
```python
headers = {'X-API-Key': 'your-api-key'}
files = {'file': open('document.pdf', 'rb')}

response = requests.post(url, files=files, headers=headers)
```

### RAG Pipeline
```python
# Full pipeline: convert → chunk → embed
url = "https://megadocs.paulocadias.com/api/pipeline"
files = {'file': open('document.pdf', 'rb')}
data = {
    'chunk_size': 512,
    'overlap': 50,
    'format': 'chromadb'
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"Chunks: {len(result['chunks'])}")
print(f"Embeddings shape: {result['embeddings_shape']}")
```

## JavaScript

### Fetch API
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('output_format', 'markdown');

const response = await fetch('https://megadocs.paulocadias.com/api/convert', {
    method: 'POST',
    body: formData
});

const data = await response.json();
if (data.success) {
    console.log(data.content);
    downloadFile(data.content, data.filename);
}
```

### With Error Handling
```javascript
try {
    const response = await fetch('/api/convert', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        if (response.status === 429) {
            const retryAfter = response.headers.get('Retry-After');
            console.log(`Rate limited. Retry after ${retryAfter}s`);
        }
        throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    console.log(data);
} catch (error) {
    console.error('Conversion failed:', error);
}
```

## cURL

### Basic Conversion
```bash
curl -X POST \
  -F "file=@document.pdf" \
  https://megadocs.paulocadias.com/api/convert
```

### Plain Text Output
```bash
curl -X POST \
  -F "file=@document.pdf" \
  -F "output_format=text" \
  https://megadocs.paulocadias.com/api/convert
```

### With API Key
```bash
curl -X POST \
  -H "X-API-Key: your-key-here" \
  -F "file=@document.pdf" \
  https://megadocs.paulocadias.com/api/convert
```

### Save to File
```bash
curl -X POST \
  -F "file=@document.pdf" \
  https://megadocs.paulocadias.com/api/convert \
  | jq -r '.content' > output.md
```

### Batch Processing
```bash
curl -X POST \
  -F "file=@documents.zip" \
  -F "webhook_url=https://your-domain.com/webhook" \
  https://megadocs.paulocadias.com/api/batch/convert
```

## Node.js

### Using axios
```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('document.pdf'));

axios.post('https://megadocs.paulocadias.com/api/convert', form, {
    headers: form.getHeaders()
})
.then(response => {
    console.log(response.data.content);
})
.catch(error => {
    console.error('Error:', error.response.data);
});
```

## Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "io"
    "mime/multipart"
    "net/http"
    "os"
)

func convertDocument(filepath string) error {
    file, err := os.Open(filepath)
    if err != nil {
        return err
    }
    defer file.Close()

    body := &bytes.Buffer{}
    writer := multipart.NewWriter(body)
    
    part, err := writer.CreateFormFile("file", filepath)
    if err != nil {
        return err
    }
    
    io.Copy(part, file)
    writer.Close()

    req, err := http.NewRequest("POST", 
        "https://megadocs.paulocadias.com/api/convert", body)
    if err != nil {
        return err
    }
    
    req.Header.Set("Content-Type", writer.FormDataContentType())
    
    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    
    if result["success"].(bool) {
        println(result["content"].(string))
    }
    
    return nil
}
```

## PHP

```php
<?php
$url = 'https://megadocs.paulocadias.com/api/convert';
$file = new CURLFile('document.pdf');

$data = array('file' => $file);

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_POST, 1);
curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$response = curl_exec($ch);
curl_close($ch);

$result = json_decode($response, true);
if ($result['success']) {
    echo $result['content'];
}
?>
```

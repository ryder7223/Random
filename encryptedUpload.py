from flask import Flask, request, send_from_directory, jsonify, Response
import secrets
import os

app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Encrypted Upload</title>
<style>
*{
    box-sizing:border-box;
}

body{
    font-family:sans-serif;
    background:#10131a;
    color:#e8ecf5;
    max-width:800px;
    margin:auto;
    padding:40px 20px;
}

.card{
    background:#181d27;
    border:1px solid #30394d;
    border-radius:16px;
    padding:30px;
    box-shadow:0 8px 30px rgba(0,0,0,.35);
}

h1{
    margin-top:0;
    font-size:28px;
}

p{
    color:#b9c2d6;
}

#drop{
    border:2px dashed #53617a;
    border-radius:12px;
    padding:45px 20px;
    text-align:center;
    cursor:pointer;
    margin-top:25px;
    transition:.2s;
}

#drop:hover,#drop.hover{
    background:#222a38;
    border-color:#7898ff;
}

input[type=file]{
    display:none;
}

button{
    margin-top:15px;
    background:#4f7cff;
    color:white;
    border:0;
    border-radius:8px;
    padding:10px 18px;
    cursor:pointer;
    font-size:15px;
}

button:hover{
    background:#638cff;
}

#status{
    margin-top:20px;
    color:#aeb8cc;
}

#uploadWrap{
    width:100%;
    height:10px;
    background:#30394d;
    border-radius:999px;
    overflow:hidden;
    margin-top:15px;
    display:none;
}

#uploadBar{
    height:100%;
    width:0%;
    background:#4f7cff;
    transition:.1s;
}

#uploads{
    margin-top:20px;
}

.uploadItem{
    margin-top:10px;
    padding:15px;
    background:#202735;
    border-radius:10px;
    word-break:break-all;
}

#link{
    margin-top:20px;
    padding:15px;
    background:#10131a;
    border-radius:8px;
    word-break:break-all;
    display:none;
}

a{
    color:#7da2ff;
}

.info{
    margin-top:25px;
    padding:15px;
    background:#202735;
    border-radius:10px;
}

@media(max-width:600px){
    body{
        padding:20px 10px;
    }

    .card{
        padding:20px;
    }
}
</style>
</head>
<body>

<div class="card">

<h1>Encrypted File Upload</h1>

<p>
Files are encrypted inside your browser before upload.
The server only receives encrypted data and never receives the encryption key.
</p>

<div id="drop">
Drag & drop files here<br><br>
<input id="file" type="file" multiple>
<button onclick="document.getElementById('file').click()">Choose Files</button>
</div>

<div id="uploadWrap">
<div id="uploadBar"></div>
</div>

<div id="status"></div>

<div id="uploads"></div>

<div class="info">
<strong>How it works</strong>
<p>
A random AES-256 encryption key is generated locally.
The key and filename are stored only inside the URL fragment, which is never sent to the server.
Anyone with the complete link can decrypt the file.
</p>
</div>

</div>

<script>

const drop=document.getElementById("drop");
const input=document.getElementById("file");
const status=document.getElementById("status");
const uploads=document.getElementById("uploads");
const uploadWrap=document.getElementById("uploadWrap");
const uploadBar=document.getElementById("uploadBar");

let activeUploads=[];


function bytesToBase64(bytes){
    return btoa(String.fromCharCode(...bytes))
        .replace(/\+/g,"-")
        .replace(/\//g,"_")
        .replace(/=/g,"");
}


function base64ToBytes(str){
    str=str.replace(/-/g,"+").replace(/_/g,"/");

    while(str.length%4)
        str+="=";

    return Uint8Array.from(
        atob(str),
        c=>c.charCodeAt(0)
    );
}


function textToBase64(text){
    return bytesToBase64(
        new TextEncoder().encode(text)
    );
}


function base64ToText(str){
    return new TextDecoder().decode(
        base64ToBytes(str)
    );
}


function updateProgress(){

    if(activeUploads.length===0){
        uploadWrap.style.display="none";
        return;
    }

    uploadWrap.style.display="block";

    let total=0;
    let loaded=0;

    for(const upload of activeUploads){
        total+=upload.total;
        loaded+=upload.loaded;
    }

    if(total){
        uploadBar.style.width=
            ((loaded/total)*100)+"%";
    }
}


async function upload(file){

    status.textContent=
        "Encrypting "+file.name+"...";


    const plain=await file.arrayBuffer();


    const key=await crypto.subtle.generateKey(
        {
            name:"AES-GCM",
            length:256
        },
        true,
        ["encrypt","decrypt"]
    );


    const rawKey=await crypto.subtle.exportKey(
        "raw",
        key
    );


    const iv=crypto.getRandomValues(
        new Uint8Array(12)
    );


    const encrypted=await crypto.subtle.encrypt(
        {
            name:"AES-GCM",
            iv:iv
        },
        key,
        plain
    );


    const output=new Uint8Array(
        iv.length+encrypted.byteLength
    );


    output.set(iv,0);

    output.set(
        new Uint8Array(encrypted),
        iv.length
    );


    status.textContent=
        "Uploading "+file.name+"...";

    const uploadState={
        loaded:0,
        total:output.length
    };

    activeUploads.push(uploadState);

    updateProgress();


    const item=document.createElement("div");

    item.className="uploadItem";

    item.innerHTML=
        "<strong>"+file.name+"</strong><br>Uploading...";


    uploads.appendChild(item);



    const json=await new Promise((resolve,reject)=>{

        const xhr=new XMLHttpRequest();


        xhr.open(
            "POST",
            "/upload"
        );


        xhr.upload.onprogress=function(event){

            if(event.lengthComputable){

                uploadState.loaded=
                    event.loaded;

                uploadState.total=
                    event.total;

                updateProgress();

            }

        };


        xhr.onload=function(){

            if(xhr.status===200){

                resolve(
                    JSON.parse(
                        xhr.responseText
                    )
                );

            }else{

                reject(
                    new Error(
                        "Upload failed"
                    )
                );

            }

        };


        xhr.onerror=function(){

            reject(
                new Error(
                    "Network error"
                )
            );

        };


        xhr.send(output);

    });



    activeUploads.splice(
        activeUploads.indexOf(uploadState),
        1
    );


    updateProgress();


    const url=
        location.origin+
        "/#"+
        json.id+
        "."+
        textToBase64(file.name)+
        "."+
        bytesToBase64(
            new Uint8Array(rawKey)
        );


    item.innerHTML=
        "<strong>"+file.name+"</strong><br>"+
        '<a href="'+url+'">'+url+"</a>";


    status.textContent=
        "Upload complete";


}



async function uploadFiles(files){

    for(const file of files){

        upload(file);

    }

}



async function download(fileId,fileName,keyString){

    const status=document.getElementById("status");

    status.textContent=
        "Downloading encrypted file...";


    const response=await fetch(
        "/download/"+fileId
    );


    const encrypted=new Uint8Array(
        await response.arrayBuffer()
    );


    const iv=encrypted.slice(
        0,
        12
    );


    const cipher=encrypted.slice(
        12
    );



    const key=await crypto.subtle.importKey(
        "raw",
        base64ToBytes(keyString),
        "AES-GCM",
        false,
        ["decrypt"]
    );


    const plain=await crypto.subtle.decrypt(
        {
            name:"AES-GCM",
            iv:iv
        },
        key,
        cipher
    );


    const blob=new Blob(
        [plain],
        {
            type:"application/octet-stream"
        }
    );


    const a=document.createElement("a");


    a.href=
        URL.createObjectURL(blob);


    a.download=fileName;


    document.body.appendChild(a);


    a.click();


    a.remove();


    URL.revokeObjectURL(
        a.href
    );


    status.textContent=
        "Download complete";

}



drop.addEventListener(
    "dragover",
    e=>{

        e.preventDefault();

        drop.classList.add(
            "hover"
        );

    }
);



drop.addEventListener(
    "dragleave",
    ()=>{

        drop.classList.remove(
            "hover"
        );

    }
);



drop.addEventListener(
    "drop",
    e=>{

        e.preventDefault();

        drop.classList.remove(
            "hover"
        );


        if(e.dataTransfer.files.length){

            uploadFiles(
                e.dataTransfer.files
            );

        }

    }
);



input.addEventListener(
    "change",
    ()=>{

        if(input.files.length){

            uploadFiles(
                input.files
            );

        }

    }
);



if(location.hash.length){

    const hash=
        location.hash.substring(1);


    const firstDot=
        hash.indexOf(".");


    const secondDot=
        hash.indexOf(
            ".",
            firstDot+1
        );


    if(
        firstDot!==-1 &&
        secondDot!==-1
    ){

        const fileId=
            hash.substring(
                0,
                firstDot
            );


        const fileName=
            base64ToText(
                hash.substring(
                    firstDot+1,
                    secondDot
                )
            );


        const key=
            hash.substring(
                secondDot+1
            );


        document.body.innerHTML=
            "<div class='card'><h1>Decrypting file...</h1><p id='status'>Please wait.</p></div>";


        download(
            fileId,
            fileName,
            key
        );

    }

}

</script>

</body>
</html>
"""

@app.route("/")
def index():
    return Response(
        HTML,
        mimetype="text/html"
    )


@app.route("/upload", methods=["POST"])
def upload():

    fileId = secrets.token_urlsafe(8)

    with open(
        os.path.join(
            UPLOAD_DIR,
            fileId
        ),
        "wb"
    ) as file:

        file.write(
            request.data
        )


    return jsonify({
        "id": fileId
    })



@app.route("/download/<fileId>")
def download(fileId):

    return send_from_directory(
        UPLOAD_DIR,
        fileId
    )



if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5021,
        ssl_context="adhoc",
        threaded=True
    )
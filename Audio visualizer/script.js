const audioContext = new (window.AudioContext || window.webkitAudioContext)();
const audioElement = document.getElementById('audioPlayer');
const audioFileInput = document.getElementById('audioFileInput');
const canvas = document.getElementById('visualizer');
const canvasContext = canvas.getContext('2d');
let source;
let analyser;

audioFileInput.addEventListener('change', function() {
    const files = this.files;
    if (files.length === 0) {
        return;
    }
    
    const audioFile = files[0];
    const url = URL.createObjectURL(audioFile);
    audioElement.src = url;
    audioElement.load();
    audioElement.play();

    if (source) {
        source.disconnect();
    }

    source = audioContext.createMediaElementSource(audioElement);
    analyser = audioContext.createAnalyser();
    source.connect(analyser);
    analyser.connect(audioContext.destination);
    analyser.fftSize = 256;

    visualize();
});

function visualize() {
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    function draw() {
        requestAnimationFrame(draw);
        
        analyser.getByteFrequencyData(dataArray);
        
        canvasContext.clearRect(0, 0, canvas.width, canvas.height);
        
        const barWidth = (canvas.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;
        
        for (let i = 0; i < bufferLength; i++) {
            barHeight = dataArray[i];
            
            const r = barHeight + (25 * (i / bufferLength));
            const g = 250 * (i / bufferLength);
            const b = 50;
            
            canvasContext.fillStyle = `rgb(${r},${g},${b})`;
            canvasContext.fillRect(x, canvas.height - barHeight / 2, barWidth, barHeight / 2);
            
            x += barWidth + 1;
        }
    }
    
    draw();
}
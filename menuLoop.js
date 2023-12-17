function playAudioLoop() {
    var a = new Audio("https://ryder7223.wdh.gg/menuLoop.mp3");

    a.addEventListener('loadedmetadata', function() {
        a.loop = true;
        a.play();
    });

    // Optionally, you can handle errors
    a.addEventListener('error', function(e) {
        console.error('Error loading audio:', e);
    });

}

playAudioLoop();

// Word cloud utilities (wordcloud2.js is loaded from CDN)

function renderWordCloud(canvasId, words) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !words || words.length === 0) return;

    // Count word frequencies
    const wordCounts = {};
    words.forEach(word => {
        const normalized = word.toLowerCase().trim();
        wordCounts[normalized] = (wordCounts[normalized] || 0) + 1;
    });

    // Convert to wordcloud2 format: [[word, weight], ...]
    const wordList = Object.entries(wordCounts).map(([text, count]) => [text, count * 20]);

    // Render the word cloud
    WordCloud(canvas, {
        list: wordList,
        gridSize: 8,
        weightFactor: 1,
        fontFamily: 'system-ui, sans-serif',
        color: function() {
            return ['#1095c1', '#4caf50', '#ff9800', '#e91e63', '#9c27b0'][Math.floor(Math.random() * 5)];
        },
        rotateRatio: 0.5,
        rotationSteps: 2,
        backgroundColor: 'transparent'
    });
}

// Crop Post Management System
class CropPostManager {
    constructor() {
        this.storageKey = 'cropPosts';
        this.loadAndDisplayPosts();
    }

    // Get all posts from localStorage
    getPosts() {
        const posts = localStorage.getItem(this.storageKey);
        return posts ? JSON.parse(posts) : [];
    }

    // Save posts to localStorage
    savePosts(posts) {
        localStorage.setItem(this.storageKey, JSON.stringify(posts));
    }

    // Add a new post
    addPost(postData) {
        const posts = this.getPosts();
        const newPost = {
            id: Date.now(), // Simple ID generation
            userId: 'currentUser', // In a real app, this would be the actual user ID
            ...postData,
            timestamp: new Date().toISOString()
        };
        posts.unshift(newPost); // Add to beginning of array
        this.savePosts(posts);
        return newPost;
    }

    // Load and display posts on the feed page
    loadAndDisplayPosts() {
        const feedContainer = document.querySelector('.feed-container');
        if (!feedContainer) return;

        const posts = this.getPosts();
        feedContainer.innerHTML = ''; // Clear existing content

        if (posts.length === 0) {
            // Show empty state message
            feedContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">🌾</div>
                    <h3>No crops available yet</h3>
                    <p>Be the first to post your crops! Click on "Post Upload" in the sidebar to get started.</p>
                    <a href="post-upload.html" class="upload-link">Upload Your First Crop</a>
                </div>
            `;
            return;
        }

        posts.forEach(post => {
            const postCard = this.createPostCard(post);
            feedContainer.appendChild(postCard);
        });

        // Add event listeners to buttons
        this.addButtonEventListeners();
    }

    // Create a post card element
    createPostCard(post) {
        const card = document.createElement('div');
        card.className = 'crop-card';
        card.dataset.postId = post.id;

        // Calculate time since posting
        const postTime = new Date(post.timestamp);
        const now = new Date();
        const timeDiff = now - postTime;
        const hoursAgo = Math.floor(timeDiff / (1000 * 60 * 60));
        const timeText = hoursAgo === 0 ? 'Just posted' : `Posted ${hoursAgo} hour${hoursAgo > 1 ? 's' : ''} ago`;

        card.innerHTML = `
            <div class="crop-card-header">
                <img src="images/profile.jpg" alt="Seller">
                <div class="user-info">
                    <span class="name">You</span>
                    <span class="time">${timeText}</span>
                </div>
            </div>
            <div class="crop-description">
                ${post.description}
            </div>
            <img src="${post.image}" class="crop-image" alt="${post.title}">
            <div class="crop-tags">
                <span class="crop-tag">${post.title}</span>
                <span class="crop-tag">${post.category}</span>
                <span class="crop-tag">${post.location}</span>
            </div>
            <div class="crop-details-row">
                <span class="detail"><span class="icon">₹</span>${post.price.replace('₹', '').replace('/kg', '')}/kg</span>
                <span class="detail"><span class="icon">📦</span>Available: ${post.available}</span>
                <span class="detail"><span class="icon">🚚</span>Delivery Available</span>
                <span class="detail"><span class="icon">📞</span>Contact Seller</span>
            </div>
            <div class="crop-actions-row">
                <span class="action">0 Likes</span>
                <span class="action">0 Comments</span>
            </div>
            <div class="crop-card-footer">
                <span class="share-link">Share</span>
            </div>
            <div class="contact-seller-section">
                <button class="btn-contact" onclick="cropManager.contactSeller(${post.id})">
                    <span class="icon">📞</span>
                    Contact Seller
                </button>
            </div>
        `;

        return card;
    }

    // Add event listeners to buttons
    addButtonEventListeners() {
        // Event listeners are added via onclick attributes in createPostCard
    }

    // Contact seller functionality
    contactSeller(postId) {
        const posts = this.getPosts();
        const post = posts.find(p => p.id === postId);
        if (post) {
            alert(`Contacting seller for: ${post.title}\nLocation: ${post.location}\nPrice: ${post.price}`);
            // Here you can implement actual contact functionality
            // Like opening a chat, sending email, etc.
        }
    }

    // Contact functionality
    contact(postId) {
        const posts = this.getPosts();
        const post = posts.find(p => p.id === postId);
        if (post) {
            alert(`General contact for: ${post.title}\nThis could open a contact form or redirect to contact page.`);
            // Here you can implement general contact functionality
        }
    }

    // Refresh the feed (useful for when new posts are added)
    refreshFeed() {
        this.loadAndDisplayPosts();
    }
}

// Initialize the crop manager when the page loads
let cropManager;
document.addEventListener('DOMContentLoaded', function() {
    cropManager = new CropPostManager();
    
    // Add refresh functionality (useful for testing)
    window.refreshCropFeed = function() {
        cropManager.refreshFeed();
    };
});

// Function to add a new post (can be called from other pages)
function addNewCropPost(postData) {
    if (cropManager) {
        cropManager.addPost(postData);
        cropManager.refreshFeed();
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CropPostManager, addNewCropPost };
}

  
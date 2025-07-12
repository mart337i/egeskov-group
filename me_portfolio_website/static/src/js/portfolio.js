// Portfolio JavaScript - Clean and Optimized

(function() {
    'use strict';

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        initNavigation();
        initScrollEffects();
        initContactForm();
        initParticles();
        removeLoadingScreen();
    });

    // Remove loading screen
    function removeLoadingScreen() {
        setTimeout(() => {
            const loadingScreen = document.getElementById('loading-screen');
            if (loadingScreen) {
                loadingScreen.style.opacity = '0';
                setTimeout(() => loadingScreen.remove(), 500);
            }
        }, 1000);
    }

    // Navigation functionality
    function initNavigation() {
        const navbar = document.querySelector('.navbar');
        const navLinks = document.querySelectorAll('.nav-link');
        
        if (!navbar || !navLinks.length) return;

        // Smooth scrolling for navigation links
        navLinks.forEach(link => {
            link.addEventListener('click', handleNavClick);
        });

        // Navbar scroll effect
        window.addEventListener('scroll', handleScroll);

        function handleNavClick(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            
            if (targetSection) {
                const offsetTop = targetSection.offsetTop - 80;
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
                
                // Update active nav link
                navLinks.forEach(l => l.classList.remove('active'));
                this.classList.add('active');
            }
        }

        function handleScroll() {
            // Navbar scroll effect
            navbar.classList.toggle('scrolled', window.scrollY > 50);
            
            // Update active nav link
            updateActiveNavLink();
        }

        function updateActiveNavLink() {
            const sections = document.querySelectorAll('section[id]');
            let current = '';
            
            sections.forEach(section => {
                const sectionTop = section.offsetTop - 100;
                const sectionHeight = section.clientHeight;
                
                if (window.scrollY >= sectionTop && window.scrollY < sectionTop + sectionHeight) {
                    current = section.getAttribute('id');
                }
            });
            
            navLinks.forEach(link => {
                link.classList.toggle('active', link.getAttribute('href') === `#${current}`);
            });
        }
    }

    // Scroll-triggered animations
    function initScrollEffects() {
        if (!('IntersectionObserver' in window)) return;

        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                    
                    // Animate counters if they exist
                    if (entry.target.classList.contains('stat-number')) {
                        animateCounter(entry.target);
                    }
                    
                    // Stop observing once animated
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });

        // Observe elements for animation
        const animateElements = document.querySelectorAll('.skill-card, .project-card, .contact-item, .about-content, .stat-number');
        animateElements.forEach(el => observer.observe(el));
    }

    // Animate counter function
    function animateCounter(element) {
        const target = parseInt(element.textContent);
        if (isNaN(target)) return;
        
        const duration = 2000;
        const step = target / (duration / 16);
        let current = 0;
        
        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(current);
            }
        }, 16);
    }

    // Contact form functionality
    function initContactForm() {
        const contactForm = document.querySelector('.contact-form');
        if (!contactForm) return;
        
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const data = Object.fromEntries(formData);
            
            // Validation
            if (!data.name || !data.email || !data.message) {
                showNotification('Udfyld venligst alle felter.', 'error');
                return;
            }
            
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(data.email)) {
                showNotification('Indtast venligst en gyldig email adresse.', 'error');
                return;
            }
            
            // Simulate form submission
            showNotification('Tak for din besked! Jeg vender tilbage hurtigst muligt.', 'success');
            this.reset();
        });
    }

    // Show notification
    function showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            background: type === 'success' ? '#10b981' : '#ef4444',
            color: 'white',
            padding: '1rem 1.5rem',
            borderRadius: '10px',
            boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
            zIndex: '1000',
            transform: 'translateX(100%)',
            transition: 'transform 0.3s ease'
        });
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => notification.style.transform = 'translateX(0)', 100);
        
        // Remove after 5 seconds
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 5000);
    }

    // Initialize floating particles
    function initParticles() {
        const heroSection = document.querySelector('.hero-section');
        if (!heroSection || window.innerWidth < 768) return;
        
        const particlesContainer = document.createElement('div');
        particlesContainer.className = 'particles-container';
        
        Object.assign(particlesContainer.style, {
            position: 'absolute',
            top: '0',
            left: '0',
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
            zIndex: '1'
        });
        
        heroSection.appendChild(particlesContainer);
        
        // Create particles
        for (let i = 0; i < 20; i++) {
            createParticle(particlesContainer);
        }
    }

    function createParticle(container) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        const size = Math.random() * 4 + 1;
        const x = Math.random() * 100;
        const y = Math.random() * 100;
        const duration = Math.random() * 20 + 10;
        
        Object.assign(particle.style, {
            position: 'absolute',
            width: `${size}px`,
            height: `${size}px`,
            background: 'rgba(99, 102, 241, 0.3)',
            borderRadius: '50%',
            left: `${x}%`,
            top: `${y}%`,
            animation: `float ${duration}s linear infinite`
        });
        
        container.appendChild(particle);
        
        // Remove and recreate particle after animation
        setTimeout(() => {
            if (container.contains(particle)) {
                container.removeChild(particle);
                createParticle(container);
            }
        }, duration * 1000);
    }

})();
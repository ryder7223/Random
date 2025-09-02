import sympy
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import math

'''
Noteworthy numbers
220: Alternates between 2 numbers
1264460: 3 way oscillation
14316: 28 way oscillation
276: Has no calculated end
6: Perfect number, stays the same forever
30: Gradual increase, followed by a spike, then plumits and steadily falls to the end
138: It's a roller coaster ride
'''

# Cache for factor sums to avoid recalculating
factor_sum_cache = {}

# Known perfect numbers for early termination
PERFECT_NUMBERS = {6, 28, 496, 8128, 33550336, 8589869056, 137438691328, 2305843008139952128, 618970019642690137449562111}

def get_factors(n):
    """Get all proper factors of n (excluding n itself) using sympy's optimized functions"""
    if n <= 1:
        return set()
    
    # Use sympy's factorint for efficient factorization
    factors = sympy.factorint(n)
    all_factors = {1}
    
    # More efficient factor generation using recursive approach
    def generate_factors(prime_factors, current_factor=1, index=0):
        if index >= len(prime_factors):
            if current_factor < n:  # Only return proper factors
                all_factors.add(current_factor)
            return
        
        prime, power = prime_factors[index]
        for p in range(power + 1):
            generate_factors(prime_factors, current_factor * (prime ** p), index + 1)
    
    # Convert factors dict to list of tuples for easier processing
    prime_factors = list(factors.items())
    generate_factors(prime_factors)
    
    return all_factors

def sum_of_factors(n):
    """Calculate sum of proper factors with caching"""
    if n in factor_sum_cache:
        return factor_sum_cache[n]
    
    if n <= 1:
        result = 0
    elif n in PERFECT_NUMBERS:
        # Perfect numbers have sum of proper factors equal to themselves
        result = n
    else:
        result = sum(get_factors(n))
    
    factor_sum_cache[n] = result
    return result

def process_number(number, mode, max_iterations):
    values = [number]  # Start with the initial number
    last_seen = None
    repeat_count = 0
    iterations = 0
    max_value = number
    
    # Print the initial number
    print(f"1. {number}")
    
    # Clear cache periodically to prevent memory issues with very long sequences
    cache_clear_threshold = 10000
    
    while number != 0:
        iterations += 1
        
        if mode == 0 and iterations >= max_iterations:
            break
        
        # Clear cache periodically to prevent memory issues
        if iterations % cache_clear_threshold == 0:
            factor_sum_cache.clear()
        
        # Use sympy's optimized isprime function
        if sympy.isprime(number):
            number = 1
        else:
            number = sum_of_factors(number)
        
        values.append(number)
        if number > max_value:
            max_value = number
        print(f"{len(values)}. {number}")
        
        if number == last_seen:
            repeat_count += 1
        else:
            repeat_count = 0
        last_seen = number
        
        if repeat_count == 3:
            break
    
    return values, max_value

def generate_gif(values, initial_number, log_scale=False, dark_mode=False):
    fig, ax = plt.subplots()
    
    # Convert values to float and handle very large numbers
    def safe_float(x):
        try:
            return float(x)
        except (OverflowError, ValueError):
            # For extremely large numbers, use a reasonable maximum
            return 1e15
    
    # Convert all values to safe floats for plotting
    plot_values = [safe_float(v) for v in values]
    
    # Dark mode settings
    if dark_mode:
        background_color = '#1e1e1e'
        text_color = 'white'
        line_color = 'lightblue'
        fig.patch.set_facecolor(background_color)
        ax.set_facecolor(background_color)
        ax.xaxis.label.set_color(text_color)
        ax.yaxis.label.set_color(text_color)
        ax.tick_params(axis='x', colors=text_color)
        ax.tick_params(axis='y', colors=text_color)
        ax.title.set_color(text_color)
        ax.grid(color='gray', linestyle='--', linewidth=0.5)
    else:
        background_color = 'white'
        text_color = 'black'
        line_color = 'red'

    ax.set_title('Value Progression', fontsize=14, pad=20)
    plt.text(0.5, 1.02, f'Measuring: {initial_number}', ha='center', va='bottom', transform=ax.transAxes, fontsize=12, color=text_color)
    ax.set_xlabel('Step', color=text_color)
    ax.set_ylabel('Value', color=text_color)
    ax.grid(True)
    line, = ax.plot([], [], color=line_color, marker='o', markersize=5)

    if log_scale:
        step_text = ax.text(0.05, 0.05, '', transform=ax.transAxes, ha='left', va='bottom', fontsize=12, bbox=dict(facecolor='black' if dark_mode else 'white', alpha=0.8), color=text_color)
        value_text = ax.text(0.05, 0.12, '', transform=ax.transAxes, ha='left', va='bottom', fontsize=12, bbox=dict(facecolor='black' if dark_mode else 'white', alpha=0.8), color=text_color)
        max_value_text = ax.text(0.05, 0.19, '', transform=ax.transAxes, ha='left', va='bottom', fontsize=12, bbox=dict(facecolor='black' if dark_mode else 'white', alpha=0.8), color=text_color)
        ax.set_yscale('log')
    else:
        step_text = ax.text(0.05, 0.95, '', transform=ax.transAxes, ha='left', va='top', fontsize=12, bbox=dict(facecolor='black' if dark_mode else 'white', alpha=0.8), color=text_color)
        value_text = ax.text(0.05, 0.88, '', transform=ax.transAxes, ha='left', va='top', fontsize=12, bbox=dict(facecolor='black' if dark_mode else 'white', alpha=0.8), color=text_color)
        max_value_text = ax.text(0.05, 0.81, '', transform=ax.transAxes, ha='left', va='top', fontsize=12, bbox=dict(facecolor='black' if dark_mode else 'white', alpha=0.8), color=text_color)
    
    max_plot_value = max(plot_values) if plot_values else 1
    
    def init():
        ax.set_xlim(0, len(plot_values))
        if log_scale:
            ax.set_ylim(1, max_plot_value)
        else:
            ax.set_ylim(min(plot_values), max_plot_value)
        step_text.set_text('Steps: 1')
        value_text.set_text(f'Value: {values[0] if values else "N/A"}')
        max_value_text.set_text(f'Max: {max_plot_value}')
        return line, step_text, value_text, max_value_text

    def update(frame):
        current_plot_values = plot_values[:frame]
        line.set_data(range(len(current_plot_values)), current_plot_values)
        ax.set_xlim(0, len(current_plot_values))
        if current_plot_values:
            if log_scale:
                ax.set_ylim(1, max(current_plot_values))
            else:
                ax.set_ylim(min(current_plot_values), max(current_plot_values))
        step_text.set_text(f'Steps: {frame}')
        value_text.set_text(f'Value: {values[frame-1] if frame > 0 else "N/A"}')
        current_max = max(current_plot_values) if frame > 0 else max_plot_value
        max_value_text.set_text(f'Max: {current_max}')
        return line, step_text, value_text, max_value_text

    anim = FuncAnimation(fig, update, frames=len(plot_values), init_func=init, blit=True)
    
    try:
        anim.save('aliquotProgression.gif', writer='imagemagick', fps=15)
    except Exception as e:
        print(f"Warning: Could not save with imagemagick ({e}), trying Pillow...")
        try:
            anim.save('aliquotProgression.gif', writer='pillow', fps=15)
        except Exception as e2:
            print(f"Warning: Could not save GIF ({e2}), saving as static plot instead...")
            # Save as static image instead
            plt.savefig('aliquotProgression.png', dpi=300, bbox_inches='tight')
            print("Static plot saved as aliquotProgression.png")
    
    plt.close(fig)  # Close the figure to free memory

if __name__ == "__main__":
    try:
        number = int(input("Enter a number: "))
        mode = int(input("Enter mode (1 for normal, 0 for limited iterations): "))
        max_iterations = int(input("Enter maximum iterations (only used if mode is 0): "))
        log_scale = int(input("Enter 1 for logarithmic scale, 0 for linear scale: "))
        dark_mode = int(input("Enter 1 for dark mode, 0 for light mode: "))
        
        values, max_value = process_number(number, mode, max_iterations)
        generate_gif(values, number, log_scale=bool(log_scale), dark_mode=bool(dark_mode))
        print("GIF generated successfully: value_progression.gif")
    except ValueError:
        print("Please enter valid integers.")
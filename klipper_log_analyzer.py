#!/usr/bin/env python3
"""
Klipper Log Analyzer Tool
A comprehensive tool to analyze Klipper 3D printer logs and provide insights.
"""

import re
import json
import argparse
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any
import statistics
import seaborn as sns

class KlipperLogAnalyzer:
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.stats_data = []
        self.mcu_configs = {}
        self.errors = []
        self.config_sections = {}
        self.timeline = []
        self.performance_metrics = defaultdict(list)
        
    def parse_log(self):
        """Parse the entire log file and extract different types of information."""
        print(f"📊 Analyzing Klipper log: {self.log_file_path}")
        
        with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
            current_config_section = None
            line_number = 0
            
            for line in file:
                line_number += 1
                line = line.strip()
                
                if not line:
                    continue
                
                # Parse different types of log entries
                self._parse_mcu_info(line, line_number)
                self._parse_stats_line(line, line_number)
                self._parse_config_section(line, line_number)
                self._parse_errors_warnings(line, line_number)
                
        print(f"✅ Parsed {line_number} lines")
        print(f"📈 Found {len(self.stats_data)} stats entries")
        print(f"🔧 Found {len(self.mcu_configs)} MCU configurations")
        print(f"⚠️  Found {len(self.errors)} errors/warnings")
        
    def _parse_mcu_info(self, line: str, line_number: int):
        """Parse MCU loading and configuration information."""
        # MCU loading pattern
        mcu_load_pattern = r"Loaded MCU '(\w+)' (\d+) commands \((.*?)\)"
        match = re.match(mcu_load_pattern, line)
        if match:
            mcu_name, commands, version_info = match.groups()
            self.mcu_configs[mcu_name] = {
                'commands': int(commands),
                'version_info': version_info,
                'line_number': line_number
            }
            self.timeline.append({
                'line': line_number,
                'type': 'mcu_load',
                'mcu': mcu_name,
                'message': line
            })
        
        # MCU configuration pattern
        mcu_config_pattern = r"MCU '(\w+)' config: (.*)"
        match = re.match(mcu_config_pattern, line)
        if match:
            mcu_name, config_data = match.groups()
            if mcu_name in self.mcu_configs:
                self.mcu_configs[mcu_name]['config'] = config_data
        
        # MCU configured pattern
        mcu_configured_pattern = r"Configured MCU '(\w+)' \((\d+) moves\)"
        match = re.match(mcu_configured_pattern, line)
        if match:
            mcu_name, moves = match.groups()
            if mcu_name in self.mcu_configs:
                self.mcu_configs[mcu_name]['moves'] = int(moves)
    
    def _parse_stats_line(self, line: str, line_number: int):
        """Parse statistics lines for performance metrics."""
        stats_pattern = r"Stats (\d+\.?\d*): (.*)"
        match = re.match(stats_pattern, line)
        if match:
            timestamp, stats_content = match.groups()
            timestamp = float(timestamp)
            
            # Parse the stats content
            stats_dict = {'timestamp': timestamp, 'line_number': line_number}
            
            # Extract key-value pairs from stats
            kv_pattern = r'(\w+)=([0-9.-]+|active|inactive|\w+)'
            for key, value in re.findall(kv_pattern, stats_content):
                try:
                    # Try to convert to float if it's a number
                    if value not in ['active', 'inactive']:
                        stats_dict[key] = float(value)
                    else:
                        stats_dict[key] = value
                except ValueError:
                    stats_dict[key] = value
            
            # Extract temperature data
            temp_pattern = r'(\w+): temp=([0-9.-]+)'
            for sensor, temp in re.findall(temp_pattern, stats_content):
                stats_dict[f'{sensor}_temp'] = float(temp)
            
            # Extract target temperatures
            target_pattern = r'(\w+): target=([0-9.-]+)'
            for sensor, target in re.findall(target_pattern, stats_content):
                stats_dict[f'{sensor}_target'] = float(target)
            
            # Extract PWM values
            pwm_pattern = r'(\w+): .*?pwm=([0-9.-]+)'
            for sensor, pwm in re.findall(pwm_pattern, stats_content):
                stats_dict[f'{sensor}_pwm'] = float(pwm)
            
            self.stats_data.append(stats_dict)
            
            # Track performance metrics
            for key in ['freq', 'sysload', 'cputime', 'memavail']:
                if key in stats_dict:
                    self.performance_metrics[key].append(stats_dict[key])
    
    def _parse_config_section(self, line: str, line_number: int):
        """Parse configuration sections from the log."""
        config_section_pattern = r'^\[([^\]]+)\]$'
        match = re.match(config_section_pattern, line)
        if match:
            section_name = match.group(1)
            self.config_sections[section_name] = {
                'line_number': line_number,
                'content': []
            }
            return section_name
        return None
    
    def _parse_errors_warnings(self, line: str, line_number: int):
        """Parse error and warning messages."""
        error_patterns = [
            r'error',
            r'warning',
            r'exception',
            r'failed',
            r'ERROR',
            r'WARNING',
            r'EXCEPTION',
            r'FAILED'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self.errors.append({
                    'line_number': line_number,
                    'type': pattern.lower(),
                    'message': line
                })
                break
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        if not self.stats_data:
            return {"error": "No statistics data found in log"}
        
        df = pd.DataFrame(self.stats_data)
        
        report = {
            'summary': {
                'total_runtime': df['timestamp'].max() - df['timestamp'].min() if len(df) > 1 else 0,
                'total_stats_entries': len(df),
                'stats_frequency': len(df) / (df['timestamp'].max() - df['timestamp'].min()) if len(df) > 1 and df['timestamp'].max() > df['timestamp'].min() else 0
            },
            'performance_metrics': {},
            'temperature_analysis': {},
            'mcu_analysis': {},
            'communication_stats': {}
        }
        
        # Performance metrics analysis
        for metric in ['freq', 'sysload', 'cputime', 'memavail']:
            if metric in df.columns:
                values = df[metric].dropna()
                if len(values) > 0:
                    report['performance_metrics'][metric] = {
                        'mean': float(values.mean()),
                        'min': float(values.min()),
                        'max': float(values.max()),
                        'std': float(values.std()) if len(values) > 1 else 0,
                        'trend': 'increasing' if values.iloc[-1] > values.iloc[0] else 'decreasing' if len(values) > 1 else 'stable'
                    }
        
        # Temperature analysis
        temp_columns = [col for col in df.columns if col.endswith('_temp')]
        for temp_col in temp_columns:
            sensor_name = temp_col.replace('_temp', '')
            temps = df[temp_col].dropna()
            if len(temps) > 0:
                report['temperature_analysis'][sensor_name] = {
                    'min_temp': float(temps.min()),
                    'max_temp': float(temps.max()),
                    'avg_temp': float(temps.mean()),
                    'temp_stability': float(temps.std()) if len(temps) > 1 else 0
                }
        
        # MCU communication analysis
        for mcu_prefix in ['mcu', 'EBBCan']:
            mcu_keys = [col for col in df.columns if col.startswith(f'{mcu_prefix}_') or col.startswith(f'canstat_{mcu_prefix}')]
            if mcu_keys:
                mcu_data = {}
                for key in mcu_keys:
                    values = df[key].dropna()
                    if len(values) > 0 and values.dtype in ['float64', 'int64']:
                        mcu_data[key] = {
                            'mean': float(values.mean()),
                            'max': float(values.max()),
                            'min': float(values.min())
                        }
                report['mcu_analysis'][mcu_prefix] = mcu_data
        
        return report
    
    def create_visualizations(self, output_dir: str = '.'):
        """Create various visualizations from the log data."""
        if not self.stats_data:
            print("❌ No stats data available for visualization")
            return
        
        df = pd.DataFrame(self.stats_data)
        
        # Set up the plotting style
        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        
        # 1. Performance metrics over time
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Klipper Performance Metrics Over Time', fontsize=16)
        
        metrics = ['freq', 'sysload', 'cputime', 'memavail']
        for i, metric in enumerate(metrics):
            if metric in df.columns:
                ax = axes[i//2, i%2]
                ax.plot(df['timestamp'], df[metric])
                ax.set_title(f'{metric.upper()} Over Time')
                ax.set_xlabel('Time (seconds)')
                ax.set_ylabel(metric)
                ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/klipper_performance_metrics.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Temperature monitoring
        temp_columns = [col for col in df.columns if col.endswith('_temp')]
        if temp_columns:
            plt.figure(figsize=(12, 6))
            for temp_col in temp_columns:
                sensor_name = temp_col.replace('_temp', '')
                plt.plot(df['timestamp'], df[temp_col], label=sensor_name.capitalize(), linewidth=2)
            
            plt.title('Temperature Monitoring Over Time')
            plt.xlabel('Time (seconds)')
            plt.ylabel('Temperature (°C)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(f'{output_dir}/klipper_temperatures.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 3. MCU Communication Health
        if 'rx_error' in df.columns and 'tx_error' in df.columns:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            
            ax1.plot(df['timestamp'], df['rx_error'], label='RX Errors', color='red')
            ax1.plot(df['timestamp'], df['tx_error'], label='TX Errors', color='orange')
            ax1.set_title('MCU Communication Errors')
            ax1.set_xlabel('Time (seconds)')
            ax1.set_ylabel('Error Count')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            if 'bytes_write' in df.columns and 'bytes_read' in df.columns:
                ax2.plot(df['timestamp'], df['bytes_write'], label='Bytes Written', alpha=0.7)
                ax2.plot(df['timestamp'], df['bytes_read'], label='Bytes Read', alpha=0.7)
                ax2.set_title('MCU Data Transfer')
                ax2.set_xlabel('Time (seconds)')
                ax2.set_ylabel('Bytes')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(f'{output_dir}/klipper_mcu_communication.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        print(f"📊 Visualizations saved to {output_dir}/")
    
    def extract_stats_to_file(self, output_file: str):
        """Extract all stats lines to a separate file."""
        stats_lines = []
        
        with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
            for line_number, line in enumerate(file, 1):
                if line.strip().startswith('Stats '):
                    stats_lines.append(f"Line {line_number}: {line.strip()}")
        
        with open(output_file, 'w') as f:
            f.write(f"# Klipper Stats Lines Extracted from {self.log_file_path}\n")
            f.write(f"# Total stats lines found: {len(stats_lines)}\n")
            f.write(f"# Extracted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for stats_line in stats_lines:
                f.write(stats_line + '\n')
        
        print(f"📤 Extracted {len(stats_lines)} stats lines to {output_file}")
        return len(stats_lines)
    
    def generate_health_report(self) -> str:
        """Generate a comprehensive health report."""
        report_lines = []
        report_lines.append("🔍 KLIPPER LOG HEALTH REPORT")
        report_lines.append("=" * 50)
        
        # MCU Health
        report_lines.append("\n🖥️  MCU INFORMATION:")
        for mcu_name, mcu_info in self.mcu_configs.items():
            report_lines.append(f"  • {mcu_name}:")
            report_lines.append(f"    - Commands: {mcu_info.get('commands', 'N/A')}")
            report_lines.append(f"    - Moves: {mcu_info.get('moves', 'N/A')}")
            report_lines.append(f"    - Version: {mcu_info.get('version_info', 'N/A')[:50]}...")
        
        # Performance Summary
        if self.stats_data:
            df = pd.DataFrame(self.stats_data)
            report_lines.append(f"\n📊 PERFORMANCE SUMMARY:")
            report_lines.append(f"  • Runtime: {df['timestamp'].max() - df['timestamp'].min():.1f} seconds")
            report_lines.append(f"  • Stats frequency: {len(df) / (df['timestamp'].max() - df['timestamp'].min()):.2f} Hz")
            
            # System load analysis
            if 'sysload' in df.columns:
                avg_load = df['sysload'].mean()
                max_load = df['sysload'].max()
                report_lines.append(f"  • System load: avg={avg_load:.2f}, max={max_load:.2f}")
                
                if max_load > 1.0:
                    report_lines.append("    ⚠️  High system load detected!")
            
            # Memory analysis
            if 'memavail' in df.columns:
                min_mem = df['memavail'].min()
                avg_mem = df['memavail'].mean()
                report_lines.append(f"  • Memory: min={min_mem/1024:.1f}MB, avg={avg_mem/1024:.1f}MB")
                
                if min_mem < 100000:  # Less than 100MB
                    report_lines.append("    ⚠️  Low memory detected!")
        
        # Error Analysis
        report_lines.append(f"\n⚠️  ERROR ANALYSIS:")
        if self.errors:
            error_types = Counter([error['type'] for error in self.errors])
            for error_type, count in error_types.items():
                report_lines.append(f"  • {error_type}: {count} occurrences")
            
            report_lines.append(f"\n📝 Recent errors:")
            for error in self.errors[-5:]:  # Last 5 errors
                report_lines.append(f"  Line {error['line_number']}: {error['message'][:80]}...")
        else:
            report_lines.append("  ✅ No errors detected!")
        
        # Communication Health
        if self.stats_data:
            df = pd.DataFrame(self.stats_data)
            report_lines.append(f"\n📡 COMMUNICATION HEALTH:")
            
            if 'rx_error' in df.columns:
                total_rx_errors = df['rx_error'].max() - df['rx_error'].min()
                total_tx_errors = df['tx_error'].max() - df['tx_error'].min() if 'tx_error' in df.columns else 0
                report_lines.append(f"  • RX errors: {total_rx_errors}")
                report_lines.append(f"  • TX errors: {total_tx_errors}")
                
                if total_rx_errors > 0 or total_tx_errors > 0:
                    report_lines.append("    ⚠️  Communication errors detected!")
                else:
                    report_lines.append("    ✅ No communication errors!")
        
        # Temperature Health
        temp_columns = [col for col in df.columns if col.endswith('_temp')] if self.stats_data else []
        if temp_columns:
            report_lines.append(f"\n🌡️  TEMPERATURE ANALYSIS:")
            for temp_col in temp_columns:
                sensor_name = temp_col.replace('_temp', '')
                temps = df[temp_col].dropna()
                if len(temps) > 0:
                    min_temp = temps.min()
                    max_temp = temps.max()
                    avg_temp = temps.mean()
                    report_lines.append(f"  • {sensor_name}: min={min_temp:.1f}°C, max={max_temp:.1f}°C, avg={avg_temp:.1f}°C")
                    
                    # Temperature warnings
                    if 'extruder' in sensor_name and max_temp > 250:
                        report_lines.append("    ⚠️  High extruder temperature!")
                    elif 'bed' in sensor_name and max_temp > 100:
                        report_lines.append("    ⚠️  High bed temperature!")
        
        report_lines.append(f"\n📈 RECOMMENDATIONS:")
        
        # Generate recommendations based on analysis
        recommendations = []
        if self.stats_data:
            df = pd.DataFrame(self.stats_data)
            
            if 'sysload' in df.columns and df['sysload'].mean() > 0.8:
                recommendations.append("Consider reducing print complexity or upgrading hardware")
            
            if 'memavail' in df.columns and df['memavail'].min() < 200000:
                recommendations.append("Monitor memory usage - consider closing unnecessary processes")
            
            if len(self.errors) > 10:
                recommendations.append("High error count detected - review printer configuration")
            
            # Communication recommendations
            if 'rx_error' in df.columns and (df['rx_error'].max() - df['rx_error'].min()) > 5:
                recommendations.append("Communication errors detected - check cables and connections")
        
        if not recommendations:
            recommendations.append("System appears healthy - no immediate concerns")
        
        for i, rec in enumerate(recommendations, 1):
            report_lines.append(f"  {i}. {rec}")
        
        report_lines.append(f"\n📅 Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return '\n'.join(report_lines)
    
    def export_data(self, output_dir: str = '.'):
        """Export analyzed data to various formats."""
        # Export stats data to CSV
        if self.stats_data:
            df = pd.DataFrame(self.stats_data)
            df.to_csv(f'{output_dir}/klipper_stats_data.csv', index=False)
            print(f"📊 Stats data exported to {output_dir}/klipper_stats_data.csv")
        
        # Export MCU configs to JSON
        with open(f'{output_dir}/klipper_mcu_configs.json', 'w') as f:
            json.dump(self.mcu_configs, f, indent=2)
        print(f"🖥️  MCU configs exported to {output_dir}/klipper_mcu_configs.json")
        
        # Export errors to JSON
        with open(f'{output_dir}/klipper_errors.json', 'w') as f:
            json.dump(self.errors, f, indent=2)
        print(f"⚠️  Errors exported to {output_dir}/klipper_errors.json")


def main():
    parser = argparse.ArgumentParser(description='Analyze Klipper log files and provide insights')
    parser.add_argument('log_file', help='Path to the Klipper log file')
    parser.add_argument('--output-dir', '-o', default='.', help='Output directory for reports and visualizations')
    parser.add_argument('--extract-stats', help='Extract stats lines to specified file')
    parser.add_argument('--no-plots', action='store_true', help='Skip generating plots')
    parser.add_argument('--report-only', action='store_true', help='Generate only text report')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = KlipperLogAnalyzer(args.log_file)
    
    # Parse the log file
    analyzer.parse_log()
    
    if args.extract_stats:
        analyzer.extract_stats_to_file(args.extract_stats)
    
    if not args.report_only:
        # Generate performance report
        perf_report = analyzer.generate_performance_report()
        with open(f'{args.output_dir}/performance_report.json', 'w') as f:
            json.dump(perf_report, f, indent=2)
        print(f"📊 Performance report saved to {args.output_dir}/performance_report.json")
        
        # Export data
        analyzer.export_data(args.output_dir)
        
        # Create visualizations
        if not args.no_plots:
            try:
                analyzer.create_visualizations(args.output_dir)
            except Exception as e:
                print(f"⚠️  Could not generate plots: {e}")
    
    # Generate and display health report
    health_report = analyzer.generate_health_report()
    print("\n" + health_report)
    
    # Save health report
    with open(f'{args.output_dir}/health_report.txt', 'w') as f:
        f.write(health_report)
    print(f"\n📋 Health report saved to {args.output_dir}/health_report.txt")


if __name__ == "__main__":
    main()

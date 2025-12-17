"""
Comparison script: Old processor vs Improved processor
"""
import json
import re
from pathlib import Path

# Import both processors
from txt_processor import IDAPATextProcessor, RegulationChunk
from improved_processor import RegulatoryDataPipeline, print_quality_report


def analyze_old_processor_chunks(chunks: list) -> dict:
    """Analyze chunks from the old processor."""
    word_counts = []
    split_lists = 0

    # Pattern for detecting list items
    list_pattern = re.compile(r'^\s*(?:\([a-z]\)|\(\d+\)|[a-z]\.|[ivx]+\.|•|-)\s', re.MULTILINE)

    for chunk in chunks:
        content = chunk.content if hasattr(chunk, 'content') else chunk.get('content', '')
        words = len(content.split())
        word_counts.append(words)

        # Check if chunk ends mid-list
        lines = content.strip().split('\n')
        if lines:
            last_line = None
            for line in reversed(lines):
                if line.strip():
                    last_line = line.strip()
                    break

            if last_line and list_pattern.match(last_line):
                # Check if it ends with proper punctuation
                if not last_line.rstrip().endswith(('.', ';', ':', '!', '?', ')', ']')):
                    split_lists += 1

    return {
        'total_chunks': len(chunks),
        'avg_words': sum(word_counts) / len(word_counts) if word_counts else 0,
        'min_words': min(word_counts) if word_counts else 0,
        'max_words': max(word_counts) if word_counts else 0,
        'median_words': sorted(word_counts)[len(word_counts)//2] if word_counts else 0,
        'split_lists': split_lists,
        'under_150': sum(1 for w in word_counts if w < 150),
        'in_150_400': sum(1 for w in word_counts if 150 <= w < 400),
        'in_400_800': sum(1 for w in word_counts if 400 <= w <= 800),
        'in_800_1200': sum(1 for w in word_counts if 800 < w <= 1200),
        'over_1200': sum(1 for w in word_counts if w > 1200),
    }


def main():
    # Paths
    base_dir = Path(__file__).parent
    raw_dir = base_dir / "data" / "raw"

    # Test document - main IDAPA file
    test_file = "IDAPA 16.txt"
    test_path = raw_dir / test_file

    if not test_path.exists():
        print(f"Test file not found: {test_path}")
        return

    print("="*70)
    print("PROCESSOR COMPARISON TEST")
    print("="*70)
    print(f"\nTest document: {test_file}")
    print(f"File size: {test_path.stat().st_size:,} bytes")

    # Read content
    with open(test_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"Total characters: {len(content):,}")
    print(f"Total words: {len(content.split()):,}")

    # =========================================================================
    # OLD PROCESSOR
    # =========================================================================
    print("\n" + "-"*70)
    print("OLD PROCESSOR (txt_processor.py)")
    print("-"*70)

    old_processor = IDAPATextProcessor(str(raw_dir), str(base_dir / "data" / "processed"))
    old_chunks = old_processor.process_file(test_file)
    old_stats = analyze_old_processor_chunks(old_chunks)

    print(f"\nChunk count:     {old_stats['total_chunks']}")
    print(f"Avg word count:  {old_stats['avg_words']:.0f}")
    print(f"Min/Max words:   {old_stats['min_words']} / {old_stats['max_words']}")
    print(f"Median words:    {old_stats['median_words']}")
    print(f"\nSize distribution:")
    print(f"  < 150 words:     {old_stats['under_150']:4d} ({old_stats['under_150']/old_stats['total_chunks']*100:5.1f}%)")
    print(f"  150-400 words:   {old_stats['in_150_400']:4d} ({old_stats['in_150_400']/old_stats['total_chunks']*100:5.1f}%)")
    print(f"  400-800 words:   {old_stats['in_400_800']:4d} ({old_stats['in_400_800']/old_stats['total_chunks']*100:5.1f}%) ← TARGET")
    print(f"  800-1200 words:  {old_stats['in_800_1200']:4d} ({old_stats['in_800_1200']/old_stats['total_chunks']*100:5.1f}%)")
    print(f"  > 1200 words:    {old_stats['over_1200']:4d} ({old_stats['over_1200']/old_stats['total_chunks']*100:5.1f}%)")
    print(f"\nSplit lists:     {old_stats['split_lists']} ({old_stats['split_lists']/old_stats['total_chunks']*100:.1f}%)")

    # =========================================================================
    # NEW PROCESSOR
    # =========================================================================
    print("\n" + "-"*70)
    print("NEW PROCESSOR (improved_processor.py)")
    print("-"*70)

    new_pipeline = RegulatoryDataPipeline()
    new_chunks = new_pipeline.process_document(content, test_file)

    # Get quality report
    report = new_pipeline.validator.validate_chunks(new_chunks)
    detailed = new_pipeline.validator.detailed_analysis(new_chunks)

    print(f"\nChunk count:     {report.total_chunks}")
    print(f"Avg word count:  {detailed['word_count_stats']['mean']:.0f}")
    print(f"Min/Max words:   {detailed['word_count_stats']['min']} / {detailed['word_count_stats']['max']}")
    print(f"Median words:    {detailed['word_count_stats']['median']}")
    print(f"\nSize distribution:")
    dist = detailed['size_distribution']
    print(f"  < 150 words:     {dist['under_150']:4d} ({dist['under_150']/report.total_chunks*100:5.1f}%)")
    print(f"  150-400 words:   {dist['150_400']:4d} ({dist['150_400']/report.total_chunks*100:5.1f}%)")
    print(f"  400-800 words:   {dist['400_800']:4d} ({dist['400_800']/report.total_chunks*100:5.1f}%) ← TARGET")
    print(f"  800-1200 words:  {dist['800_1200']:4d} ({dist['800_1200']/report.total_chunks*100:5.1f}%)")
    print(f"  > 1200 words:    {dist['over_1200']:4d} ({dist['over_1200']/report.total_chunks*100:5.1f}%)")
    print(f"\nSplit lists:     {report.chunks_with_split_lists} ({report.chunks_with_split_lists/report.total_chunks*100:.1f}%)")

    # =========================================================================
    # COMPARISON SUMMARY
    # =========================================================================
    print("\n" + "="*70)
    print("COMPARISON SUMMARY")
    print("="*70)

    print(f"\n{'Metric':<25} {'Old':>12} {'New':>12} {'Change':>12}")
    print("-"*61)

    chunk_change = report.total_chunks - old_stats['total_chunks']
    print(f"{'Chunk count':<25} {old_stats['total_chunks']:>12} {report.total_chunks:>12} {chunk_change:>+12}")

    avg_change = detailed['word_count_stats']['mean'] - old_stats['avg_words']
    print(f"{'Avg words/chunk':<25} {old_stats['avg_words']:>12.0f} {detailed['word_count_stats']['mean']:>12.0f} {avg_change:>+12.0f}")

    old_target = old_stats['in_400_800'] / old_stats['total_chunks'] * 100
    new_target = dist['400_800'] / report.total_chunks * 100
    print(f"{'% in target range':<25} {old_target:>11.1f}% {new_target:>11.1f}% {new_target-old_target:>+11.1f}%")

    old_split = old_stats['split_lists'] / old_stats['total_chunks'] * 100
    new_split = report.chunks_with_split_lists / report.total_chunks * 100
    print(f"{'% split lists':<25} {old_split:>11.1f}% {new_split:>11.1f}% {new_split-old_split:>+11.1f}%")

    # Show sample chunks from new processor
    print("\n" + "-"*70)
    print("SAMPLE CHUNKS FROM NEW PROCESSOR")
    print("-"*70)

    for i, chunk in enumerate(new_chunks[:3]):
        print(f"\n[Chunk {i+1}]")
        print(f"ID: {chunk.chunk_id}")
        print(f"Section: {chunk.section_number} - {chunk.section_title}")
        print(f"Words: {chunk.word_count} | Category: {chunk.category}")
        print(f"Lists intact: {chunk.has_complete_lists} | Boundary: {chunk.semantic_boundary}")
        preview = chunk.content[:300].replace('\n', ' ')
        print(f"Preview: {preview}...")


if __name__ == "__main__":
    main()

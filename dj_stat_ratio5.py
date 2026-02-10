import pandas as pd
import re
import sys
import os

def get_dominant_speaker(speaker_str):
    if not isinstance(speaker_str, str): return None
    m = re.search(r"(SPEAKER_\d+)", speaker_str)
    return m.group(1) if m else None

def calculate_stats_multi_guest(df):
    """
    다중 게스트 지원 로직 (V3):
    1. 발화량 1위 = DJ
    2. DJ 제외 Interaction 1위(Top Guest)를 찾음
    3. Top Guest의 20% 이상 활동했으면 서브 게스트로 인정
    4. [안전장치] 비율과 상관없이 Interaction이 15회 이상이면 무조건 게스트
    """
    # 1. Dominant Speaker 추출
    df['Dominant_Speaker'] = df.apply(
        lambda row: get_dominant_speaker(row.get('Speakers', '')) if row['Type'] == 'speech' else None,
        axis=1
    )
    
    # 2. 발화량으로 DJ 선정
    duration_stats = {}
    for _, row in df.iterrows():
        if row['Type'] != 'speech': continue
        spk = row['Dominant_Speaker']
        if spk:
            duration_stats[spk] = duration_stats.get(spk, 0.0) + row['Duration']
            
    if not duration_stats: return pd.DataFrame()
    
    sorted_durations = sorted(duration_stats.items(), key=lambda x: x[1], reverse=True)
    dj_id = sorted_durations[0][0]
    dj_duration = sorted_durations[0][1]
    print(f"👑 DJ Identified: {dj_id} (Duration: {dj_duration:.1f}s)")
    
    # 3. DJ와의 Interaction 카운트
    speaker_indices = {spk: [] for spk in duration_stats.keys()}
    for idx, row in df.iterrows():
        if row['Type'] != 'speech': continue
        spk = row['Dominant_Speaker']
        if spk:
            speaker_indices[spk].append(idx)
    
    interaction_counts = {}
    for spk, indices in speaker_indices.items():
        if spk == dj_id: 
            interaction_counts[spk] = 0
            continue
        
        count = 0
        for idx in indices:
            # 앞뒤 3칸 내에 DJ 감지
            for offset in [-3, -2, -1, 1, 2, 3]:
                neighbor_idx = idx + offset
                if 0 <= neighbor_idx < len(df):
                    neighbor_spk = df.iloc[neighbor_idx].get('Dominant_Speaker')
                    if neighbor_spk == dj_id:
                        count += 1
                        break
        interaction_counts[spk] = count

    # 4. 게스트 판별 (핵심 로직 개선)
    candidates = [(spk, cnt) for spk, cnt in interaction_counts.items() if spk != dj_id]
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    guest_list = []
    
    if candidates:
        top_guest_spk, top_guest_cnt = candidates[0]
        
        # [조건 1] 최소 기준: 너무 적으면(7회 미만) 무조건 광고
        MIN_ABSOLUTE_THRESHOLD = 12
        
        # [조건 2] 상대 기준: 1등 게스트의 20% 수준은 되어야 함
        RELATIVE_RATIO = 0.2
        
        # [조건 3] 프리패스: 15회 이상이면 비율 상관없이 합격 (안전장치)
        FREE_PASS_THRESHOLD = 20
        
        cutoff_value = max(MIN_ABSOLUTE_THRESHOLD, top_guest_cnt * RELATIVE_RATIO)
        
        print(f"\n📊 Interaction Analysis:")
        print(f"   Benchmark (Top Guest): {top_guest_spk} ({top_guest_cnt} interactions)")
        print(f"   Cutoff Line: {cutoff_value:.1f} (or > {FREE_PASS_THRESHOLD} interactions)")
        
        for spk, cnt in candidates:
            is_guest = False
            reason = ""
            
            if cnt >= FREE_PASS_THRESHOLD:
                is_guest = True
                reason = "High Interaction (Free Pass)"
            elif cnt >= cutoff_value:
                is_guest = True
                reason = "Passed Relative Cutoff"
            
            if is_guest:
                guest_list.append(spk)
                print(f"   ✅ GUEST: {spk:<12} | {cnt:>3} interactions | {reason}")
            else:
                print(f"   ❌ AD   : {spk:<12} | {cnt:>3} interactions | Too low")
    
    # 5. 결과 생성
    results = []
    for spk, total_dur in sorted_durations:
        if spk == dj_id:
            role = "DJ"
        elif spk in guest_list:
            role = "GUEST"
        else:
            role = "AD_SPEAKER"
        
        ratio_to_dj = (total_dur / dj_duration * 100) if dj_duration > 0 else 0.0
        interact_count = interaction_counts.get(spk, 0)
        
        results.append({
            'Speaker': spk,
            'Role': role,
            'Total_Duration': round(total_dur, 2),
            'Ratio_to_DJ': f"{ratio_to_dj:.1f}%",
            'Interaction_Count': interact_count
        })
    
    return pd.DataFrame(results)

# ==========================================
# MAIN
# ==========================================
def main():
    if len(sys.argv) != 2:
        print("Usage: python dj_stat_interaction.py <YYYYMMDD>")
        sys.exit(1)

    date = sys.argv[1]
    # ★ 본인 경로에 맞게 수정 ★
    base_dir = f"/mnt/home_dnlab/jhjung/radio/baechulsu/{date}/transcript"

    input_csv = os.path.join(base_dir, f"{date}_with_speaker_ratio.csv")
    output_csv = os.path.join(base_dir, f"{date}-dj_stats.csv")

    if not os.path.exists(input_csv):
        print(f"❌ Input not found: {input_csv}")
        sys.exit(1)

    print(f"📥 Loading {input_csv}...")
    df = pd.read_csv(input_csv)

    print("📊 Analysis: Multi-Guest Support Logic (V3)")
    stats_df = calculate_stats_multi_guest(df)
    
    print("\n" + "="*70)
    print(stats_df.head(15).to_string(index=False)) # 상위 15명만 출력
    print("="*70)
    
    stats_df.to_csv(output_csv, index=False)
    print(f"\n💾 Saved to {output_csv}")

if __name__ == "__main__":
    main()
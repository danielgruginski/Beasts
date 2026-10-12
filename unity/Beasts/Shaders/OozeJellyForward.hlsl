// The jelly's forward shading, shared by its far-side and near-side passes (OozeJelly.shader). Included after the
// shader's HLSLINCLUDE block (Core.hlsl, the texture, UnityPerMaterial, Wobble).
#ifndef OOZE_JELLY_FORWARD_INCLUDED
#define OOZE_JELLY_FORWARD_INCLUDED

#define _ALPHAPREMULTIPLY_ON 1          // URP's BRDF scales the diffuse by the alpha, not the specular
#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

struct JAttributes
{
    float4 positionOS : POSITION;
    float3 normalOS   : NORMAL;
    float2 uv         : TEXCOORD0;
    UNITY_VERTEX_INPUT_INSTANCE_ID
};

struct JVaryings
{
    float4 positionCS : SV_POSITION;
    float3 positionWS : TEXCOORD0;
    half3  normalWS   : TEXCOORD1;
    float2 uv         : TEXCOORD2;
    half   fogFactor  : TEXCOORD3;
    UNITY_VERTEX_INPUT_INSTANCE_ID
    UNITY_VERTEX_OUTPUT_STEREO
};

JVaryings JellyVert(JAttributes a)
{
    JVaryings o = (JVaryings)0;
    UNITY_SETUP_INSTANCE_ID(a);
    UNITY_TRANSFER_INSTANCE_ID(a, o);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
    float3 n = TransformObjectToWorldNormal(a.normalOS);
    float3 ws = Wobble(TransformObjectToWorld(a.positionOS.xyz), n);
    o.positionWS = ws;
    o.positionCS = TransformWorldToHClip(ws);
    o.normalWS = n;
    o.uv = TRANSFORM_TEX(a.uv, _BaseMap);
    o.fogFactor = ComputeFogFactor(o.positionCS.z);
    return o;
}

// The masks to a colour (ooze_paint.shell_material builds the same in Blender): tone through thin, mid and core;
// creases toward the crevice colour; detail lightens lumps and darkens the streaks.
half3 JellyColour(half4 m)
{
    half3 c = m.r < 0.5 ? lerp(_ThinColor.rgb, _MidColor.rgb, m.r * 2) : lerp(_MidColor.rgb, _CoreColor.rgb, m.r * 2 - 1);
    c = lerp(c, _CreviceColor.rgb, 1 - smoothstep(0.55, 0.95, m.g));
    return c * (0.75 + 0.25 * m.g) * (0.55 + 0.9 * m.b);
}

// facing: +1 the near side, -1 the far side (seen from inside, its normal turned toward the eye); fade scales it.
half4 JellyShade(JVaryings i, half facing, half fade)
{
    UNITY_SETUP_INSTANCE_ID(i);
    half4 m = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv);
    half4 tex = half4(JellyColour(m), m.a);
    float3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
    float3 n = NormalizeNormalPerPixel(i.normalWS) * facing;
    half rim = pow(1 - saturate(dot(n, v)), _FresnelPower);
    half alpha = saturate(tex.a * _Opacity + rim * _Fresnel);

    InputData d = (InputData)0;
    d.positionWS = i.positionWS;
    d.positionCS = i.positionCS;
    d.normalWS = n;
    d.viewDirectionWS = v;
    d.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
    d.fogCoord = InitializeInputDataFog(float4(i.positionWS, 1.0), i.fogFactor);
    d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
    d.bakedGI = SampleSH(n);
    d.shadowMask = half4(1, 1, 1, 1);

    SurfaceData s = (SurfaceData)0;
    s.albedo = tex.rgb;
    s.metallic = 0;
    s.smoothness = _Smoothness;
    s.occlusion = 1;
    s.alpha = alpha;
    s.emission = tex.rgb * (_Glow * alpha);

    half4 c = UniversalFragmentPBR(d, s);       // premultiplied: rgb already carries the alpha (diffuse only)
    c.rgb = MixFog(c.rgb, d.fogCoord);
    return half4(c.rgb, alpha) * fade;
}

#endif

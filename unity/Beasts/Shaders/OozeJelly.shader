// The dungeon ooze's see-through jelly (Beasts, ooze_paint.shell_material is the Blender preview of it). Two passes
// over the same mesh, alpha blended without depth writes: the far side first (back faces, normal turned toward the
// eye), then the near side, so the shell reads as a solid lump with the contents (a separate opaque mesh) inside.
// The colour is the material's (or a renderer's MaterialPropertyBlock, OozeLook): T_Ooze holds masks (R tone: thin -> mid
// -> core by the jelly's thickness, G shade: creases dark, B detail, A opacity), mapped through four colours, so any
// ooze colour is a material setting. Opacity = the texture's alpha (thick core denser, pod tips and the skirt's edge
// clear) x _Opacity + a fresnel rim. Premultiplied
// (URP Lit's "Premultiply"): the diffuse fades with the opacity, the highlights don't, so it stays wet and glossy where
// it is clear. A faint glow of its own colour keeps the shaded side from going black; a small vertex wobble; a shadow
// dithered by the opacity (a transparent shell casts none otherwise).
Shader "Beasts/OozeJelly"
{
    Properties
    {
        [MainTexture][NoScaleOffset] _BaseMap ("Masks: tone, shade, detail, opacity (linear)", 2D) = "white" {}
        _ThinColor ("Thin (tips, edges)", Color) = (0.651, 0.831, 0.333, 1)
        _MidColor ("Mid", Color) = (0.310, 0.549, 0.110, 1)
        _CoreColor ("Core (thick)", Color) = (0.173, 0.353, 0.071, 1)
        _CreviceColor ("Creases", Color) = (0.090, 0.196, 0.031, 1)
        _Opacity ("Opacity", Range(0, 2)) = 1
        _Fresnel ("Rim opacity", Range(0, 1)) = 0.45
        _FresnelPower ("Rim falloff", Range(0.5, 8)) = 2.5
        _Smoothness ("Smoothness", Range(0, 1)) = 0.9
        _Glow ("Glow (its own colour)", Range(0, 1)) = 0.08
        _BackFade ("Far side opacity", Range(0, 1)) = 0.75
        _Wobble ("Wobble (m)", Range(0, 0.05)) = 0.008
        _WobbleSpeed ("Wobble speed", Range(0, 6)) = 1.6
        _ShadowDensity ("Shadow density", Range(0, 1)) = 0.6
    }
    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" "RenderType" = "Transparent" "Queue" = "Transparent" "IgnoreProjector" = "True" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _ThinColor, _MidColor, _CoreColor, _CreviceColor;
            half _Opacity, _Fresnel, _FresnelPower, _Smoothness, _Glow, _BackFade, _Wobble, _WobbleSpeed, _ShadowDensity;
        CBUFFER_END

        float3 Wobble(float3 posWS, float3 nWS)
        {
            float t = _Time.y * _WobbleSpeed;
            float w = sin(posWS.x * 3.1 + t) * sin(posWS.z * 2.7 - t * 0.8) + 0.5 * sin(posWS.y * 4.3 + t * 1.3);
            return posWS + nWS * (w * _Wobble);
        }
        ENDHLSL

        Pass
        {
            Name "JellyFarSide"
            Tags { "LightMode" = "SRPDefaultUnlit" }        // drawn before UniversalForward for the same renderer
            Cull Front
            ZWrite Off
            Blend One OneMinusSrcAlpha
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex JellyVert
            #pragma fragment FragFar
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Fog.hlsl"
            #pragma multi_compile_instancing
            #include "OozeJellyForward.hlsl"
            half4 FragFar(JVaryings i) : SV_Target { return JellyShade(i, -1, _BackFade); }
            ENDHLSL
        }

        Pass
        {
            Name "JellyNearSide"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite Off
            Blend One OneMinusSrcAlpha
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex JellyVert
            #pragma fragment FragNear
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Fog.hlsl"
            #pragma multi_compile_instancing
            #include "OozeJellyForward.hlsl"
            half4 FragNear(JVaryings i) : SV_Target { return JellyShade(i, 1, 1); }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On ZTest LEqual ColorMask 0 Cull Off
            HLSLPROGRAM
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct SAttributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct SVaryings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            SVaryings ShadowVert(SAttributes a)
            {
                SVaryings o;
                UNITY_SETUP_INSTANCE_ID(a);
                float3 ws = TransformObjectToWorld(a.positionOS.xyz);
                float3 n = TransformObjectToWorldNormal(a.normalOS);
                ws = Wobble(ws, n);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 ld = normalize(_LightPosition - ws);
            #else
                float3 ld = _LightDirection;
            #endif
                float4 cs = TransformWorldToHClip(ApplyShadowBias(ws, n, ld));
            #if UNITY_REVERSED_Z
                cs.z = min(cs.z, UNITY_NEAR_CLIP_VALUE);
            #else
                cs.z = max(cs.z, UNITY_NEAR_CLIP_VALUE);
            #endif
                o.positionCS = cs;
                o.uv = TRANSFORM_TEX(a.uv, _BaseMap);
                return o;
            }

            half4 ShadowFrag(SVaryings i) : SV_Target
            {
                // a 4x4 ordered dither: the shadow map's filtering averages it into a partial shadow
                static const float B[16] = { 0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5 };
                uint2 p = uint2(i.positionCS.xy) & 3;
                half a = saturate(SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).a * _Opacity + 0.15) * _ShadowDensity;
                clip(a - (B[p.y * 4 + p.x] + 0.5) / 16.0);
                return 0;
            }
            ENDHLSL
        }
    }
}

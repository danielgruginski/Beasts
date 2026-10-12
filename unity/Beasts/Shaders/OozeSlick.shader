// The dungeon ooze's slime trail (OozeTrail): one flat sheet over the floor round the ooze, showing a wetness field the
// trail paints into (R8, tied to the world and wrapping: _Field is sampled at worldXZ * _FieldScale). Where the field
// passes the edge threshold there is slime, so splats close together merge into one wet patch with smooth necks
// between them (no alpha piling up where they overlap), and as the field dries the edges creep in and the patch breaks
// into puddles before it goes. The field's slope tilts the normal, so the edge carries a bead of highlight.
// Premultiplied like the jelly: the diffuse fades with the opacity, the highlights only with the coverage. Drawn
// before the other transparents (Transparent-10): the jelly blends over it.
Shader "Beasts/OozeSlick"
{
    Properties
    {
        [NoScaleOffset] _Field ("Wetness field (R)", 2D) = "black" {}
        _FieldScale ("1 / field size (1/m)", Float) = 0.078
        _FieldTexel ("One field texel (uv)", Float) = 0.0078
        _FieldMax ("Field value at texture 1", Float) = 1.3
        _Color ("Slime colour", Color) = (0.20, 0.36, 0.08, 1)
        _Edge ("Edge (from, to)", Vector) = (0.30, 0.40, 0, 0)
        _Opacity ("Opacity (drying, fresh)", Vector) = (0.20, 0.60, 0, 0)
        _Smoothness ("Smoothness", Range(0, 1)) = 0.92
        _Bump ("Edge bump", Range(0, 20)) = 4
        _Border ("Sheet border fade (uv)", Range(0.001, 0.5)) = 0.08
    }
    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" "RenderType" = "Transparent" "Queue" = "Transparent-10" "IgnoreProjector" = "True" }

        Pass
        {
            Name "Slick"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            ZWrite Off
            Blend One OneMinusSrcAlpha
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Fog.hlsl"
            #pragma multi_compile_instancing

            #define _ALPHAPREMULTIPLY_ON 1          // URP's BRDF scales the diffuse by the alpha, not the specular
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE2D(_Field); SAMPLER(sampler_Field);
            CBUFFER_START(UnityPerMaterial)
                float _FieldScale, _FieldTexel, _FieldMax;
                half4 _Color;
                float4 _Edge, _Opacity;
                half _Smoothness, _Bump, _Border;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 uv         : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float2 uv         : TEXCOORD1;
                half   fogFactor  : TEXCOORD2;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings Vert(Attributes a)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(a);
                UNITY_TRANSFER_INSTANCE_ID(a, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.positionWS = TransformObjectToWorld(a.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.uv = a.uv;
                o.fogFactor = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            float Field(float2 uv) { return SAMPLE_TEXTURE2D(_Field, sampler_Field, uv).r * _FieldMax; }

            half4 Frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                float2 fu = i.positionWS.xz * _FieldScale;
                float f = Field(fu);
                float2 b = min(i.uv, 1 - i.uv);
                half border = smoothstep(0, _Border, min(b.x, b.y));
                half cover = smoothstep(_Edge.x, _Edge.y, f) * border;
                clip(cover - 0.002);
                float fx = Field(fu + float2(_FieldTexel, 0)) - Field(fu - float2(_FieldTexel, 0));
                float fz = Field(fu + float2(0, _FieldTexel)) - Field(fu - float2(0, _FieldTexel));
                float3 n = normalize(float3(-fx * _Bump, 1, -fz * _Bump));
                half alpha = cover * lerp(_Opacity.x, _Opacity.y, saturate((f - _Edge.x) / max(1 - _Edge.x, 0.01)));

                InputData d = (InputData)0;
                d.positionWS = i.positionWS;
                d.positionCS = i.positionCS;
                d.normalWS = n;
                d.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                d.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                d.fogCoord = InitializeInputDataFog(float4(i.positionWS, 1.0), i.fogFactor);
                d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                d.bakedGI = SampleSH(n);
                d.shadowMask = half4(1, 1, 1, 1);

                SurfaceData s = (SurfaceData)0;
                s.albedo = _Color.rgb;
                s.metallic = 0;
                s.smoothness = _Smoothness;
                s.occlusion = 1;
                s.alpha = alpha;

                half4 c = UniversalFragmentPBR(d, s);       // premultiplied: the diffuse carries the alpha
                c.rgb = MixFog(c.rgb, d.fogCoord) * cover;   // the highlights end where the slime does
                return half4(c.rgb, alpha);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
